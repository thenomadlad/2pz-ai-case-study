"""Lounge features and growth areas from the v3 data, at any assumption levels (see SOURCES.md,
"Market model"). Fast enough to rerun on every app click: level-independent lookups are built once
per V3."""
import re
import statistics
from collections import Counter, defaultdict
from functools import cache

import numpy as np
import pandas as pd

from src.config import REPO_ROOT

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
REF_UNIT_M2 = 150
REF_UNIT_WHY = ("Lounge floor areas aren't public: 150 m2 is an assumed reference unit. One size "
                "for every site, so it sets the level of women-per-rent, never the ranking.")
_PREP: dict[int, tuple[V3, dict]] = {}


def women_per_rent_k(women: float, rent_m2: float | None) -> float | None:
    """Addressable women per AED 1,000 of annual rent for a REF_UNIT_M2 unit; None without a rent."""
    if rent_m2 is None or rent_m2 != rent_m2 or rent_m2 <= 0:
        return None
    return women / (rent_m2 * REF_UNIT_M2 / 1000)


MIN_RENT_COVERAGE = 0.5
MIN_RENT_COVERAGE_WHY = ("A catchment or area shop rent needs cells holding half its women: a rent from a "
                         "sliver of the cells (Saih Shuaib 1: 10%) describes those cells, not the place.")


def _shop_rent(cs: list[str], w: dict, shop: dict) -> tuple[float | None, float]:
    """Women-weighted median shop rent over these cells (None under MIN_RENT_COVERAGE of the
    women), and the share of women it covers."""
    obs = [c for c in cs if shop.get(c) is not None and shop[c] == shop[c]]
    total = sum(w[c] for c in cs)
    cov = sum(w[c] for c in obs) / total if total else 0.0
    return (weighted_median([shop[c] for c in obs], [w[c] for c in obs]) if cov >= MIN_RENT_COVERAGE else None,
            cov)


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
         "shop_source": c.shop_rent_source.to_dict() if "shop_rent_source" in c else {},
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
    shop = v3.cells.shop_rent_m2.to_dict() if "shop_rent_m2" in v3.cells else {}
    aw_s = women * affluence_weight(rent, women, a.affluence_elasticity[levels.affluence])
    aw = aw_s.to_dict()
    sv = _served(v3, a, aw_s, levels, closed, leave_one_out=areas)
    site = _site_served(v3, a, aw_s, closed)
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
        cell_ = p["cell"]
        site_cell = next((c for c in cs if abs(cell_[c]["lat"] - lo.lat) <= 0.01
                          and abs(cell_[c]["lng"] - lo.lng) <= 0.01), None)
        rent_ = shop.get(site_cell) if site_cell else None
        rent_ = None if rent_ is None or rent_ != rent_ else float(rent_)
        c_rent, c_cov = _shop_rent(cs, w, shop)
        source = p["shop_source"].get(site_cell, "none") if rent_ is not None else "none"
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
            served_women=sv["served"].get(b), absorbed_share=sv["absorbed"].get(b),
            site_served=site.get(b), performance_vs_site=sv["served"].get(b, 0.0) / site[b] if site.get(b) else None,
            site_rent_m2=rent_, site_rent_source=source,
            catchment_shop_rent_m2=c_rent, shop_rent_coverage=c_cov,
            women_per_rent_k=women_per_rent_k(addressable, rent_),
            est_customers=0.0 if b in NOT_SCORED else cap * addressable, not_scored=b in NOT_SCORED))
    feats = _lounge_costs(feats)
    if not areas:
        return feats, []

    cell = p["cell"]
    groups = defaultdict(list)
    for c, x in w.items():
        # Unnamed cells (only their emirate's name: no OSM place within 3 km) make no area: nobody can
        # act on them yet. They still count in lounge catchments, overlap and population totals.
        if x > 0 and cell[c].get("name_source") != "emirate":
            groups[(cell[c]["name"], cell[c]["emirate"])].append(c)
    lounges = [lo for lo in lounges if lo.branch_id not in NOT_SCORED]     # never an area's nearest lounge
    lats, lngs = np.array([lo.lat for lo in lounges]), np.array([lo.lng for lo in lounges])
    out = []
    for (name, emirate), cs in groups.items():
        # one area per OSM place name, contiguous or not
        out.append(_area(_slug(f"{name} {emirate}"), name, emirate, sorted(cs, key=p["rc"].get),
                         w, aw, rents, shop, p, a, lounges, lats, lngs, sv["cells"].unserved,
                         sv["cells"].served_lounges))
    out = _area_what_ifs(v3, a, aw_s, out, feats, closed)
    return feats, sorted(out, key=lambda x: -x.women)


FITOUT_AED_M2 = 3_000
FITOUT_YEARS = 5
FITOUT_WHY = ("Assumed, not sourced (2026-10-11): a salon fit-out of about AED 3,000/m² (AED 280/sqft), "
              "written off over 5 years, on the 150 m² reference unit: about AED 90k a year on top of rent.")


def site_cost_k(rent_m2: float | None) -> float | None:
    """Annual cost of a REF_UNIT_M2 site, AED 1k: rent plus amortised fit-out; None without a rent."""
    if rent_m2 is None or rent_m2 != rent_m2:
        return None
    return (rent_m2 * REF_UNIT_M2 + FITOUT_AED_M2 * REF_UNIT_M2 / FITOUT_YEARS) / 1000


SITE_REFERENCE = REPO_ROOT / "data/seed/v3/site_reference.csv"
MIN_REF_SITES = 50
SITE_REFERENCE_WHY = (
    "Labels are judged within each emirate, against its market of salon SITES, frozen: every real "
    "(non-imputed) premium competitor salon in the served model, Bedashing excluded (1,123 sites; "
    "data/seed/v3/site_reference.csv, built once 2026-10-11 by scripts/build_site_reference.py). Per site: "
    "the cell shop rent, and the women a typical lounge would serve there with all our lounges open. Never "
    "against our own lounges (Fujairah and Ras Al Khaimah have one, Sharjah two), and nothing we open or "
    "close moves it. Demand = the share of the emirate's reference sites a site out-serves; an emirate with "
    f"under {MIN_REF_SITES} reference sites (Ajman 38, Ras Al Khaimah 33, Fujairah 18, Umm Al Quwain 5) uses "
    "the UAE-wide set instead: a percentile among a few dozen sites moves several points per site. Rent "
    "ratio = the emirate's median shop rent at its reference sites ÷ the site's shop rent (its own "
    "emirate's median even under 50 sites: rents are an emirate-level market, and a UAE-wide median "
    "would call every northern site cheap). Rebuild (and say so) only when the served model, demand "
    "or salon data change.")


@cache
def site_reference() -> pd.DataFrame:
    """The frozen reference set of competitor salon sites (SITE_REFERENCE_WHY)."""
    return pd.read_csv(SITE_REFERENCE, comment="#")


@cache
def _ref() -> dict:
    r = site_reference()
    served = {e: np.sort(g.ref_served.to_numpy()) for e, g in r.groupby("emirate")}
    return {"served": served, "uae": np.sort(r.ref_served.to_numpy()), "rents": np.sort(r.shop_rent_m2.to_numpy()),
            "rent_median": r.groupby("emirate").shop_rent_m2.median().to_dict(),
            "uae_rent_median": float(r.shop_rent_m2.median())}


def _below(sorted_ref: np.ndarray, x: float) -> float:
    """Share of the reference strictly below x (empirical percentile, 0..1)."""
    return float(np.searchsorted(sorted_ref, x, side="left") / len(sorted_ref))


def site_signals(emirate: str, served: float | None, rent_m2: float | None) -> dict:
    """A site's place in the frozen reference (SITE_REFERENCE_WHY): demand_pct within its emirate's
    salon sites (UAE-wide under MIN_REF_SITES), rent_ratio against its emirate's median rent, and
    the UAE-wide percentiles of both for context."""
    r = _ref()
    own = r["served"].get(emirate)
    use_own = own is not None and len(own) >= MIN_REF_SITES
    rent = None if rent_m2 is None or rent_m2 != rent_m2 or rent_m2 <= 0 else rent_m2
    return {"demand_ref": emirate if use_own else "UAE",
            "demand_pct": None if served is None else _below(own if use_own else r["uae"], served),
            "demand_pct_uae": None if served is None else _below(r["uae"], served),
            "rent_ratio": None if rent is None else r["rent_median"].get(emirate, r["uae_rent_median"]) / rent,
            "rent_pct_uae": None if rent is None else _below(r["rents"], rent)}


def _lounge_costs(feats):
    """Site cost, and the site's demand and rent against the frozen salon-site reference."""
    return [f.model_copy(update={"site_cost_k": site_cost_k(f.site_rent_m2),
                                 **site_signals(f.emirate, f.site_served, f.site_rent_m2)}) for f in feats]


TYPICAL_REVIEWS = 757
TYPICAL_RATING = 4.6
TYPICAL_WHY = ("The typical lounge every what-if opens (area what-ifs, site_served, the salon-site reference) is "
               "frozen at the 2026-10-11 baseline: the median reviews (757) and rating (4.6) over the open scored "
               "lounges, as data/seed/v3/site_reference.csv was built. A live median drifted when a lounge "
               "closed (khaleej-al-arabi 0.3504 -> 0.3488 with no change of its own), so closing one lounge "
               "could move another's call; frozen, it can't. Re-freeze only with a rebuilt reference.")


def _site_served(v3, a, aw_s, closed) -> dict[str, float]:
    """site_served per open scored lounge (src/model/served.site_served); cached on the demand and closures."""
    from src.model.served import site_served
    key = ("site", id(v3), hash(aw_s.to_numpy().tobytes()), closed)
    if key not in _SERVED:
        _SERVED[key] = site_served(v3, a, aw_s, TYPICAL_REVIEWS, TYPICAL_RATING, closed=closed, not_scored=frozenset(NOT_SCORED))
    return _SERVED[key]


def _area_what_ifs(v3, a, aw_s, areas, feats, closed):
    """Open a typical lounge at each area worth a look (5k+ women, a residential name): what it serves,
    what it takes from our lounges, and its demand and rent against the salon-site reference."""
    from src.model.growth import NON_RESIDENTIAL, SKIP_UNDER_WOMEN
    from src.model.served import what_if_open
    out = []
    for ar in areas:
        if ar.women < SKIP_UNDER_WOMEN or NON_RESIDENTIAL.search(ar.name):
            out.append(ar)
            continue
        # keyed on the demand itself: affluence weighting keeps the total, so a sum would collide across levels
        key = ("open", id(v3), ar.area_id, hash(aw_s.to_numpy().tobytes()), closed)
        if key not in _SERVED:
            _SERVED[key] = what_if_open(v3, a, aw_s, ar.lat, ar.lng, TYPICAL_REVIEWS, TYPICAL_RATING, closed=closed,
                                        not_scored=frozenset(NOT_SCORED))
        w = _SERVED[key]
        cost = site_cost_k(ar.shop_rent_m2)
        out.append(ar.model_copy(update={
            "new_site_served": w["served"], "new_site_taken": w["taken_from_lounges"], "new_site_net": w["net_new"],
            "site_cost_k": cost, **site_signals(ar.emirate, w["served"], ar.shop_rent_m2)}))
    return out


_SERVED: dict = {}


def _served(v3, a, aw_s, levels, closed, leave_one_out: bool = True) -> dict:
    """Huff served/unserved demand; depends only on demand levels and closures, so cached on those.
    Without leave_one_out (level_flips: absorbed_share isn't scored) the full result is reused if
    cached, else a lighter one is cached apart."""
    from src.model.served import served
    key = (id(v3), levels.worker_share, levels.affluence, closed)
    if key in _SERVED:
        return _SERVED[key]
    if leave_one_out:
        _SERVED[key] = served(v3, a, aw_s, closed=closed, not_scored=frozenset(NOT_SCORED))
        return _SERVED[key]
    light = (*key, "no-loo")
    if light not in _SERVED:
        _SERVED[light] = served(v3, a, aw_s, closed=closed, not_scored=frozenset(NOT_SCORED), leave_one_out=False)
    return _SERVED[light]


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


def _area(area_id, name, emirate, piece, w, aw, rents, shop, p, a, lounges, lats, lngs, unserved=None,
          ours=None) -> Area:
    cell, women = p["cell"], sum(w[c] for c in piece)
    lat = sum(w[c] * cell[c]["lat"] for c in piece) / women
    lng = sum(w[c] * cell[c]["lng"] for c in piece) / women
    sat = _saturation(piece, w, p, a)
    a_rent, a_cov = _shop_rent(piece, w, shop)
    src = p["shop_source"]
    rented = sum(w[c] for c in piece if src.get(c, "none") != "none")
    fallback = sum(w[c] for c in piece if src.get(c) == "emirate_median") / rented if rented else 0.0
    d = haversine_km(lat, lng, lats, lngs)
    j = int(d.argmin()) if len(d) else None
    return Area(area_id=area_id, name=name, emirate=emirate, lat=lat, lng=lng, women=women,
                addressable_women=sum(aw[c] for c in piece), **_affluence(piece, w, rents, women), cells=len(piece),
                worker_share=sum(cell[c]["adults_worker"] for c in piece) / sum(cell[c]["adults"] for c in piece),
                premium_salons=sat["n"], premium_reviews_per_1k=sat["per_1k"], full_circle_share=sat["fcs"],
                unserved_women=float(sum(unserved.get(c, 0.0) for c in piece)) if unserved is not None else 0.0,
                served_ours=float(sum(ours.get(c, 0.0) for c in piece)) if ours is not None else 0.0,
                shop_rent_m2=a_rent, shop_rent_coverage=a_cov, shop_rent_fallback_share=fallback,
                women_per_rent_k=women_per_rent_k(sum(aw[c] for c in piece), a_rent),
                data_coverage=sat["cw"] / women, cell_ids=piece,
                nearest_lounge_id=lounges[j].branch_id if j is not None else "",
                nearest_lounge_km=float(d[j]) if j is not None else float("nan"))
