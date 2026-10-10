"""The market model: women 15+ per cell, premium substitutes, and a lounge's capture against them."""
import math
import re
import statistics

SALON_TYPES = {"beauty_salon", "hair_salon", "nail_salon", "beautician", "hair_care"}
MALE_NAME = re.compile(r"\b(gents?|men|man|barber|barbershop|barbers)\b"
                       r"|حلاق|رجال", re.IGNORECASE)   # Arabic: barber / barbering, men's


def residential_share(women: float, adults: float, worker_adults: float, worker_share: float) -> float:
    """Female share outside worker housing that keeps the emirate's total women unchanged."""
    rest = adults - worker_adults
    return float(min(1.0, max(0.0, (women - worker_share * worker_adults) / rest))) if rest else 0.0


def market_women(adults, worker_adults, worker_share, resid_share):
    return worker_share * worker_adults + resid_share * (adults - worker_adults)


def women_15plus(cells, emirates, worker_share: float):
    """Women 15+ per cell (pandas): worker housing at worker_share, the rest of each emirate
    rebalanced so its WorldPop female total is unchanged. `emirates` is emirates.csv indexed
    by emirate."""
    resid = {e: residential_share(r.women_worldpop, r.adults, r.worker_adults, worker_share)
             for e, r in emirates.iterrows()}
    return market_women(cells.adults, cells.adults_worker, worker_share, cells.emirate.map(resid))


def coverage_k(substitutes: list[dict], share: float) -> int:
    """How many of the (review-sorted) substitutes it takes to hold `share` of their reviews."""
    total, run = sum(_reviews(s) for s in substitutes), 0
    for k, s in enumerate(substitutes, start=1):
        run += _reviews(s)
        if run >= share * total:
            return k
    return len(substitutes)


def recall_multiplier(full_share: float, recall: float) -> float:
    """Correction for salons the search missed. Where a circle comes back full (Google's cap of
    20), it may hold more; calibrated on the fully swept Al Barsha tile, our circles found `recall`
    (~0.66) of premium reviews where they were all full. Scale linearly with the share of a
    catchment's circles that were full: 1.0 where none were, 1/recall where all were."""
    return 1 + full_share * (1 / recall - 1)


def capture_by_coverage(lounge_reviews: int, premium: list[dict], coverage: float,
                        multiplier: float) -> tuple[float, int]:
    """Capture against the review-sorted premium salons that hold `coverage` of the premium
    reviews found, with their reviews scaled up by the recall `multiplier`. Returns (capture, k)."""
    k = coverage_k(premium, coverage)
    if not k:
        return 1.0, 0
    subs = multiplier * sum(_reviews(s) for s in premium[:k])
    return lounge_reviews / (lounge_reviews + subs), k


def excluded_reason(r: dict) -> str:
    if r.get("status") and r["status"] != "OPERATIONAL":
        return "not-operational"
    if r.get("primary_type") == "barber_shop" or MALE_NAME.search(r.get("name") or ""):
        return "men-only"
    if r.get("primary_type") not in SALON_TYPES:
        return "not-a-salon"
    return ""


def _reviews(r: dict) -> int:
    return int(float(r.get("review_count") or 0))


def premium_substitutes(candidates: list[dict], k: int, min_rating: float,
                        price_levels: list[str]) -> list[dict]:
    """Top k by reviews among premium candidates: Google price in price_levels or, where Google
    has no price, reviews >= the candidates' median and rating >= min_rating."""
    if not candidates:
        return []
    median = statistics.median(_reviews(c) for c in candidates)

    def premium(c):
        if c.get("price_level"):
            return c["price_level"] in price_levels
        rating = c.get("rating")
        return (rating not in (None, "") and float(rating) >= min_rating
                and _reviews(c) > 0 and _reviews(c) >= median)

    return sorted((c for c in candidates if premium(c)), key=_reviews, reverse=True)[:k]


def capture(lounge_reviews: int, substitutes: list[dict]) -> float:
    """Lounge reviews / (lounge + substitutes' reviews); 1.0 when nothing competes."""
    if not substitutes:
        return 1.0
    total = lounge_reviews + sum(_reviews(s) for s in substitutes)
    return lounge_reviews / total if total else 0.0


def weighted_median(values, weights) -> float | None:
    """Median of `values` with each counted `weights` times; None when there is nothing to weigh."""
    pairs = sorted((v, w) for v, w in zip(values, weights) if w > 0 and not math.isnan(v))
    total = sum(w for _, w in pairs)
    if not total:
        return None
    run = 0.0
    for v, w in pairs:
        run += w
        if run >= total / 2:
            return float(v)


def affluence_weight(rent, women, elasticity: float):
    """Per cell (pandas, same index): (rent / women-weighted median rent) ** elasticity, clipped (before rescaling) to
    [0.25, 4] and rescaled so the women-weighted mean over cells with a rent is 1. Cells without an
    observed rent (NaN) get 1.0: affluence unknown, weighted neutral. Elasticity 0 turns it off."""
    out = rent.isna() * 0 + 1.0                # 1.0 everywhere, same index
    obs = rent.notna() & (women > 0)
    if not elasticity or not obs.any():
        return out
    w = (rent[obs] / weighted_median(rent[obs], women[obs])) ** elasticity
    w = w.clip(0.25, 4)
    out[obs] = w * women[obs].sum() / (w * women[obs]).sum()
    return out
