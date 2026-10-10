"""Lounge scorecard: four signals on FIXED scales, weighted, PROTECT / HOLD / SHRINK.

Fixed scales so a lounge's score doesn't move when a sibling opens or closes. Anchors were set
from the v3 features at medium levels (notebooks/decisions.ipynb); each `why` says why. They
were reviewed by the user on 2026-10-09 (rating at half weight; flips lower confidence). Demand
reads affluence-weighted women since 2026-10-10 (notebooks/affluence.ipynb); same anchors.
"""
from collections import Counter
from dataclasses import dataclass, fields
from itertools import product

from src.models import Decision, Levels, LoungeFeatures


@dataclass(frozen=True)
class Signal:
    name: str
    field: str
    label: str
    worst: float  # value that scores 0
    best: float   # value that scores 1
    why: str
    weight: float = 1.0


SIGNALS: tuple[Signal, ...] = (
    Signal("demand", "addressable_women", "Addressable women 15+ in the 15-min catchment", 0, 200_000,
           "Affluence-weighted (Dubai rents; elsewhere a woman counts 1). Lounges range 23k-321k "
           "addressable women, median 107k (raw: 23k-272k, median 107k); 200k is where the four big "
           "Dubai lounges sit, weighted or not, and one lounge can't absorb more, so extra women stop counting."),
    Signal("cannibalisation", "shared_share", "Share of catchment women another lounge also reaches",
           1.0, 0.0,
           "Already a 0-100% share: 0% means no sibling reaches this lounge's women. Abu Dhabi "
           "city lounges mostly sit at 82-100%."),
    Signal("capture", "capture", "Lounge reviews as a share of lounge + premium substitutes", 0, 0.15,
           "Median 6.5% over the scored lounges; 15% is about the best reliable lounge (al-taif-mall, 14%). In a thin "
           "premium market (under 10 premium salons) a share of a tiny pool is noisy, so the score is pulled "
           "toward 0.5 in proportion: with n premium salons it keeps n/10 of its distance from 0.5. A blend, "
           "not a cliff, so one more salon can't swing the score."),
    Signal("rating", "rating_gap", "Rating minus the substitutes' median rating (stars)", -0.3, 0.3,
           "Gaps run -0.2 to +0.3, median -0.1: most lounges rate slightly below their premium "
           "substitutes; ±0.3 stars covers the whole range. Half weight: Google ratings come in "
           "0.1 steps, so the gap takes only a handful of values.", 0.5),
)

PROTECT_AT = 0.65
SHRINK_AT = 0.35
THRESHOLDS_WHY = (
    f"PROTECT at a composite of {PROTECT_AT} or more means the lounge clears the bar on most "
    f"signals, not just one. SHRINK at {SHRINK_AT} or less means it is weak on most signals. "
    "Everything between is HOLD: with no revenue or rent data, strong calls need the signals to agree."
)
AXES = tuple(f.name for f in fields(Levels))     # travel, coverage, worker_share, affluence
COMBOS = 3 ** len(AXES)                          # 81 level combinations
FLIP_LOW_SHARE = 1 / 3   # of the combinations: a call that flips this often is low confidence
FLIP_LOW = round(FLIP_LOW_SHARE * COMBOS)        # 27 of 81
FLIP_WHY = (f"A lounge whose action changes in {FLIP_LOW} or more (a third) of the {COMBOS} "
            "combinations of travel time, competitor coverage, worker-housing share and affluence "
            "weighting depends on the assumptions more than on the data, so its call is low confidence.")
NEUTRAL = 0.5  # a missing rating gap never scores as the worst; thin-market capture is pulled toward it
THIN_MARKET = 10
THIN_MARKET_WHY = ("Under 10 premium salons, capture is a share of a tiny pool, so it is noisy: its score keeps "
                   "only premium_pool / 10 of its distance from neutral (0 salons: neutral). A blend replaces "
                   "the old cliff, where three 5-review salons swung al-dhafra by 0.14 (SANITY_CHECKS SC4). "
                   "A thin market stays a low-confidence reason.")
WEIGHT_STEPS = (0.75, 1.25)
WEIGHT_WHY = ("The weights are a design choice, not data. Each signal's weight is moved ×0.75 and ×1.25, "
              "one at a time (8 variants); a call that changes under any of them depends on the weighting, "
              "so it is low confidence. The decision lines aren't varied: within 0.05 of one is already low.")
NO_FINANCIALS = ("No revenue, rent or footfall data: this scores location and market position "
                 "only, not return on invested capital.")


def score(signal: Signal, value: float | None) -> float:
    if value is None:
        return NEUTRAL
    return max(0.0, min(1.0, (value - signal.worst) / (signal.best - signal.worst)))


LOW_MARGIN = 0.05   # composite this close to a line: low confidence
HIGH_MARGIN = 0.10  # this far from both lines: high confidence


def _confidence(composite: float, low: bool) -> str:
    margin = min(abs(composite - PROTECT_AT), abs(composite - SHRINK_AT))
    if low or margin < LOW_MARGIN:
        return "low"
    return "high" if margin >= HIGH_MARGIN else "medium"


def _action(composite: float) -> str:
    return "PROTECT" if composite >= PROTECT_AT else "SHRINK" if composite <= SHRINK_AT else "HOLD"


def _composite(scores: dict[str, float], weights: dict[str, float]) -> float:
    return sum(weights[n] * scores[n] for n in weights) / sum(weights.values())


def weight_flips(scores: dict[str, float]) -> list[str]:
    """The weight variants (each signal ×0.75 or ×1.25, one at a time) that change the call."""
    base = {s.name: s.weight for s in SIGNALS}
    action = _action(_composite(scores, base))
    out = []
    for s in SIGNALS:
        for step in WEIGHT_STEPS:
            new = _action(_composite(scores, {**base, s.name: s.weight * step}))
            if new != action:
                out.append(f"{s.name} weight ×{step:g} → {new}")
    return out


def _decide(f: LoungeFeatures, flips: int | None) -> Decision:
    if f.not_scored:
        return Decision(branch_id=f.branch_id, action="NOT SCORED", confidence="low",
                        rationale="Not scored: this lounge serves travellers, not the women in its catchment.",
                        key_drivers=[], caveats=[])
    scores = {s.name: score(s, getattr(f, s.field)) for s in SIGNALS}
    if f.thin_premium_market:
        scores["capture"] = NEUTRAL + (scores["capture"] - NEUTRAL) * min(1.0, f.premium_pool / THIN_MARKET)
    composite = _composite(scores, {s.name: s.weight for s in SIGNALS})
    action = _action(composite)
    caveats = [NO_FINANCIALS]
    if f.thin_premium_market:
        caveats.append(f"Thin premium market ({f.premium_pool} premium salons): capture's score pulled toward "
                       f"neutral, keeping {f.premium_pool}/{THIN_MARKET} of its distance from 0.5.")
    if f.rating_gap is None:
        caveats.append("No rating gap (missing rating or no rated substitutes): scored neutral.")
    flippy = flips is not None and flips >= FLIP_LOW
    if flippy:
        caveats.append(f"The call changes in {flips} of {COMBOS} assumption combinations.")
    wflips = weight_flips(scores)
    if wflips:
        caveats.append("The call depends on the signal weights: it changes with " + "; ".join(wflips) + ".")
    return Decision(
        branch_id=f.branch_id, action=action, weight_flips=wflips,
        confidence=_confidence(composite, f.thin_premium_market or f.rating_gap is None or flippy or bool(wflips)),
        rationale=(f"Composite {composite:.2f} across demand, cannibalisation, capture and rating "
                   f"(PROTECT ≥ {PROTECT_AT}, SHRINK ≤ {SHRINK_AT})."),
        key_drivers=sorted(scores, key=lambda n: abs(scores[n] - NEUTRAL), reverse=True)[:2],
        caveats=caveats, composite=round(composite, 4), scores={k: round(v, 4) for k, v in scores.items()})


def decide(features: list[LoungeFeatures], flips: dict[str, int] | None = None) -> list[Decision]:
    """`flips`: per lounge, how many of the 81 level combinations change its action (level_flips)."""
    return [_decide(f, (flips or {}).get(f.branch_id)) for f in features]


def level_flips(v3, assumptions, levels, closed=frozenset()) -> dict[str, int]:
    """How many of the 81 level combinations give each lounge a different action than `levels`."""
    from src.features.lounges import build  # here, not at the top: build doesn't need the scorecard

    def actions(lv):
        return {d.branch_id: d.action for d in decide(build(v3, assumptions, lv, closed, areas=False)[0])}

    base = actions(levels)
    out = Counter()
    for lv in product(("low", "medium", "high"), repeat=len(AXES)):
        for b, a in actions(Levels(*lv)).items():
            out[b] += a != base[b]
    return {b: out[b] for b in base}


def counts(decisions: list[Decision]) -> dict[str, int]:
    """PROTECT / HOLD / SHRINK counts; NOT SCORED lounges are left out."""
    c = Counter(d.action for d in decisions)
    return {a: c[a] for a in ("PROTECT", "HOLD", "SHRINK")}
