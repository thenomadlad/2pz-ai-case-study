"""Lounge features and growth areas from the v3 data, at any assumption levels (see SOURCES.md,
"Market model"). Fast enough to rerun on every app click: level-independent lookups are built once
per V3."""
import re
import statistics
from collections import Counter, defaultdict

import numpy as np

from src.data_v3 import V3
from src.market import (
    _reviews,
    affluence_weight,
    capture_by_coverage,
    coverage_k,
    premium_substitutes,
    recall_multiplier,
    weighted_median,
    women_15plus,
)
from src.model.scorecard import THIN_MARKET
from src.models import Area, BaselineAssumptions, Levels, LoungeFeatures

NOT_SCORED = {"zayed-international-airport"}
NOT_SCORED_WHY = ("Serves travellers, not the women in its catchment, so it gets no call and is left out "
                  "of every comparison: it is no lounge's sibling (shared catchment) or premium substitute, "
                  "no area's nearest lounge, and its catchment cells are open to growth areas.")
MIN_RATING_REVIEWS = 20
MIN_RATING_REVIEWS_WHY = ("The rating gap compares a lounge with the median rating of its whole premium pool, "
                          "counting salons with at least 20 reviews: a Google rating from fewer moves 0.1+ "
                          "stars on a single review. The whole pool, not the top-k substitutes, because k "
                          "grows with the pool, so one added salon could shift which salons count and "
                          "raise a lounge's score (sanity check SC4, run 2).")
_PREP: dict[int, tuple[V3, dict]] = {}


def _prep(v3: V3) -> dict:
    """Catchments per level, competitor salons per searched cell, and circles per cell."""
    hit = _PREP.get(id(v3))
    if hit and hit[0] is v3:
        return hit[1]
    c, ci = v3.cells, v3.circles
    ids = c.index.to_numpy()
    s_, w_, n_, e_ = (c[k].to_numpy() for k in ("south", "west", "north", "east"))
    clat, clng = ci.lat.to_numpy(float)[:, None], ci.lng.to_numpy(float)[:, None]
    cos, r = np.cos(np.radians(clat)), ci.radius_m.to_numpy(float)[:, None] / 111_000

    def in_disk(lat, lng):     # circles x cells; lat-scaled disks, as in scripts/fetch_salons.py
        return (lat - clat) ** 2 + ((lng - clng) * cos) ** 2 <= r ** 2

    covered = in_disk(c.lat.to_numpy(), c.lng.to_numpy())
    touch = in_disk(np.clip(clat, s_, n_), np.clip(clng, w_, e_))
    owns = (s_ <= clat) & (clat < n_) & (w_ <= clng) & (clng < e_)
    cov = covered.any(0)
    sal = v3.salons[(v3.salons.excluded_reason == "") & ~v3.salons.is_bedashing.astype(bool)]
    slat, slng = sal.lat.to_numpy()[:, None], sal.lng.to_numpy()[:, None]
    inbox = (s_ <= slat) & (slat < n_) & (w_ <= slng) & (slng < e_) & cov    # salons x cells
    salons = defaultdict(list)
    for row, i, ok in zip(sal.reset_index().to_dict("records"), inbox.argmax(1), inbox.any(1)):
        if ok:
            salons[ids[i]].append(row)
    p = {"catch": {lv: g.groupby("branch_id").cell_id.agg(list).to_dict() for lv, g in v3.catchment.groupby("level")},
         "covered": dict(zip(ids, cov)), "salons": salons, "full": ci.full.astype(str).eq("True").to_numpy(),
         "owns": {cid: np.flatnonzero(owns[:, j]) for j, cid in enumerate(ids) if cov[j]},
         "touch": {cid: np.flatnonzero(touch[:, j]) for j, cid in enumerate(ids) if cov[j]},
         "rc": {cid: tuple(map(int, re.match(r"r(\d+)c(\d+)", cid).groups())) for cid in ids},
         "cell": c[["name", "emirate", "lat", "lng", "adults", "adults_worker"]
                   + (["name_source"] if "name_source" in c else [])].to_dict("index")}
    _PREP[id(v3)] = (v3, p)
    return p


def haversine_km(lat, lng, lats, lngs):
    """Great-circle km; numpy, so lats/lngs can be arrays or scalars."""
    p1, p2 = np.radians(lat), np.radians(lats)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lngs - lng) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9\u0600-\u06ff]+", "-", s.lower()).strip("-")   # keeps Arabic-only names apart


def _candidates(v3: V3, levels: Levels, closed: frozenset[str], branch_id: str) -> list[dict]:
    gone = {lo.place_id for lo in v3.lounges if lo.branch_id in closed or lo.branch_id in NOT_SCORED}
    return [s for s in v3.candidates[(branch_id, levels.travel)] if s["place_id"] not in gone]


def premium_pool(v3: V3, a: BaselineAssumptions, levels: Levels, closed: frozenset[str],
                 branch_id: str) -> list[dict]:
    """A lounge's premium salons in its catchment at this travel level, most-reviewed first."""
    cands = _candidates(v3, levels, closed, branch_id)
    return premium_substitutes(cands, len(cands), a.premium_min_rating, a.comparable_price_levels)


def substitutes(v3: V3, a: BaselineAssumptions, levels: Levels, closed: frozenset[str],
                branch_id: str) -> list[dict]:
    """The premium salons a lounge's capture is measured against (the most-reviewed ones holding
    competitor_coverage of the pool's reviews), each with `premium_because`. Copies: safe to keep."""
    pool = premium_pool(v3, a, levels, closed, branch_id)
    median = statistics.median(_reviews(s) for s in _candidates(v3, levels, closed, branch_id)) if pool else 0
    return [{**s, "premium_because": (
                f"Google price: {s['price_level']}" if s["price_level"] else
                f"no Google price; {_reviews(s):,} reviews ≥ the catchment median ({median:,.0f}) "
                f"and {float(s['rating']):.1f}★ ≥ {a.premium_min_rating}")}
            for s in pool[:coverage_k(pool, a.competitor_coverage[levels.coverage])]]


def build(v3: V3, assumptions: BaselineAssumptions, levels: Levels = Levels(),  # noqa: B008 (frozen)
          closed: frozenset[str] = frozenset(), areas: bool = True) -> tuple[list[LoungeFeatures], list[Area]]:
    """Features of every open lounge, and the growth areas no open lounge reaches (`areas=False`
    skips them: level_flips needs only the lounges)."""
    a, p = assumptions, _prep(v3)
    women = women_15plus(v3.cells, v3.emirates, a.worker_housing_female_share[levels.worker_share])
    rent = v3.cells.rent_observed
    w, rents = women.to_dict(), rent.to_dict()
    aw = (women * affluence_weight(rent, women, a.affluence_elasticity[levels.affluence])).to_dict()
    lounges = [lo for lo in v3.lounges if lo.branch_id not in closed]
    catch = {lo.branch_id: p["catch"].get(levels.travel, {}).get(lo.branch_id, []) for lo in lounges}
    reach = Counter(c for b, cs in catch.items() if b not in NOT_SCORED for c in cs)   # scored lounges only

    feats = []
    for lo in lounges:
        b, cs = lo.branch_id, catch[lo.branch_id]
        women_ = sum(w[c] for c in cs)
        addressable = sum(aw[c] for c in cs)
        prem = premium_pool(v3, a, levels, closed, b)
        mult = recall_multiplier(v3.full_share[(b, levels.travel)], a.search_recall)
        cap, k = capture_by_coverage(lo.review_count, prem, a.competitor_coverage[levels.coverage], mult)
        rated = [float(s["rating"]) for s in prem
                 if s.get("rating") not in (None, "") and _reviews(s) >= MIN_RATING_REVIEWS]
        med = statistics.median(rated) if rated else None
        sat = _saturation(cs, w, p, a)
        feats.append(LoungeFeatures(
            branch_id=b, name=lo.name, emirate=lo.emirate, lat=lo.lat, lng=lo.lng, rating=lo.rating,
            review_count=lo.review_count, catchment_women=women_, addressable_women=addressable,
            **_affluence(cs, w, rents, women_), catchment_cells=len(cs),
            # cells another scored lounge also reaches (reach counts this one too, unless it isn't scored)
            shared_share=sum(w[c] for c in cs if reach[c] > (b not in NOT_SCORED)) / women_ if women_ else 0.0,
            capture=cap, substitutes_k=k, recall_multiplier=mult, premium_pool=len(prem),
            thin_premium_market=len(prem) < THIN_MARKET, premium_reviews_per_1k=sat["per_1k"],
            substitutes_median_rating=med,
            rating_gap=lo.rating - med if lo.rating is not None and med is not None else None,
            est_customers=0.0 if b in NOT_SCORED else cap * addressable, not_scored=b in NOT_SCORED))
    if not areas:
        return feats, []

    cell = p["cell"]
    groups = defaultdict(list)
    for c, x in w.items():
        # Unnamed cells (only their emirate's name: no OSM place within 3 km) make no area: nobody can
        # act on them yet. They still count in lounge catchments, overlap and population totals.
        if x > 0 and c not in reach and cell[c].get("name_source") != "emirate":
            groups[(cell[c]["name"], cell[c]["emirate"])].append(c)
    lounges = [lo for lo in lounges if lo.branch_id not in NOT_SCORED]     # never an area's nearest lounge
    lats, lngs = np.array([lo.lat for lo in lounges]), np.array([lo.lng for lo in lounges])
    out = []
    for (name, emirate), cs in groups.items():
        # one area per OSM place name, contiguous or not
        out.append(_area(_slug(f"{name} {emirate}"), name, emirate, sorted(cs, key=p["rc"].get),
                         w, aw, rents, p, a, lounges, lats, lngs))
    return feats, sorted(out, key=lambda x: -x.women)


def _affluence(cs: list[str], w: dict, rents: dict, women: float) -> dict:
    """Women-weighted median observed rent over these cells, and the share of women it covers."""
    obs = [c for c in cs if not np.isnan(rents[c])]
    return {"affluence_rent": weighted_median([rents[c] for c in obs], [w[c] for c in obs]),
            "affluence_coverage": sum(w[c] for c in obs) / women if women else 0.0}


def _saturation(cells: list[str], w: dict, p: dict, a: BaselineAssumptions) -> dict:
    """Premium saturation over the searched ones of these cells: premium salons, their reviews (scaled
    up by the recall correction) per 1k women in those cells, the share of their circles that came back
    full, and those cells' women. One method for growth areas and lounge catchments (rubric MO8)."""
    covered = [c for c in cells if p["covered"][c]]
    cw = sum(w[c] for c in covered)
    if not covered:
        return {"n": None, "per_1k": None, "fcs": None, "cw": cw}
    cands = [s for c in covered for s in p["salons"][c]]
    prem = premium_substitutes(cands, len(cands), a.premium_min_rating, a.comparable_price_levels)
    circ = set().union(*(p["owns"][c] for c in covered)) or set().union(*(p["touch"][c] for c in covered))
    fcs = float(np.mean(p["full"][sorted(circ)]))
    per_1k = sum(_reviews(s) for s in prem) * recall_multiplier(fcs, a.search_recall) / (cw / 1000) if cw else None
    return {"n": len(prem), "per_1k": per_1k, "fcs": fcs, "cw": cw}


def _area(area_id, name, emirate, piece, w, aw, rents, p, a, lounges, lats, lngs) -> Area:
    cell, women = p["cell"], sum(w[c] for c in piece)
    lat = sum(w[c] * cell[c]["lat"] for c in piece) / women
    lng = sum(w[c] * cell[c]["lng"] for c in piece) / women
    sat = _saturation(piece, w, p, a)
    d = haversine_km(lat, lng, lats, lngs)
    j = int(d.argmin()) if len(d) else None
    return Area(area_id=area_id, name=name, emirate=emirate, lat=lat, lng=lng, women=women,
                addressable_women=sum(aw[c] for c in piece), **_affluence(piece, w, rents, women), cells=len(piece),
                worker_share=sum(cell[c]["adults_worker"] for c in piece) / sum(cell[c]["adults"] for c in piece),
                premium_salons=sat["n"], premium_reviews_per_1k=sat["per_1k"], full_circle_share=sat["fcs"],
                data_coverage=sat["cw"] / women, cell_ids=piece,
                nearest_lounge_id=lounges[j].branch_id if j is not None else "",
                nearest_lounge_km=float(d[j]) if j is not None else float("nan"))
