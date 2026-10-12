import itertools

import pandas as pd
import pytest

from src.data_v3 import LEVELS, V3, load_v3
from src.features.lounges import build
from src.market import women_15plus
from src.models import BaselineAssumptions, Levels, Lounge

ASSUMPTIONS = BaselineAssumptions()
C1, C2, C3, C5, FAR = "r0c1", "r0c2", "r0c3", "r0c5", "r5c5"


def by_id(rows):
    return {r.branch_id: r for r in rows}


def _cell(cid, adults, name="Town"):
    row, col = map(int, cid[1:].split("c"))
    lat, lng = 25 + row * 0.02, 55 + col * 0.02
    return {"cell_id": cid, "lat": lat, "lng": lng, "south": lat - 0.01, "west": lng - 0.01,
            "north": lat + 0.01, "east": lng + 0.01, "emirate": "Dubai", "name": name,
            "adults": adults, "adults_worker": 0, "rent_observed": float("nan")}


def _lounge(b, cid, reviews, rating=4.8):
    c = _cell(cid, 0)
    return Lounge(branch_id=b, title=b, name=b, emirate="Dubai", lat=c["lat"], lng=c["lng"],
                  place_id=f"p-{b}", rating=rating, review_count=reviews, address="")


def _salon(pid, cid, reviews, price="expensive", rating=4.5, bedashing=False):
    c = _cell(cid, 0)
    return {"place_id": pid, "name": pid, "lat": c["lat"], "lng": c["lng"], "rating": rating,
            "review_count": reviews, "price_level": price, "excluded_reason": "", "is_bedashing": bedashing}


def _v3(lounges, cells, catch, salons, candidates, circles=()):
    cells = pd.DataFrame(cells).set_index("cell_id")
    emirates = pd.DataFrame([{"emirate": "Dubai", "adults": cells.adults.sum(),
                              "women_worldpop": cells.adults.sum() / 2, "worker_adults": 0}]).set_index("emirate")
    catchment = pd.DataFrame([{"cell_id": c, "level": lv, "branch_id": b}
                              for b, cs in catch.items() for c in cs for lv in LEVELS],
                             columns=["cell_id", "level", "branch_id"])
    salons_df = pd.DataFrame(salons, columns=list(_salon("x", C1, 0))).set_index("place_id")
    circ = pd.DataFrame(list(circles), columns=["purpose", "lat", "lng", "radius_m", "results", "full"])
    return V3(lounges, cells, emirates, catchment, salons_df, circ, {},
              {(lo.branch_id, lv): candidates.get(lo.branch_id, []) for lo in lounges for lv in LEVELS},
              {(lo.branch_id, lv): 0.0 for lo in lounges for lv in LEVELS})


@pytest.fixture
def tiny_v3():
    """a reaches C1, C2; b reaches C2, C3; b is one of a's premium candidates; C5 and FAR are unreached."""
    a, b = _lounge("a", C1, 100), _lounge("b", C3, 500)
    s1 = _salon("s1", C1, 300)
    bs = _salon("p-b", C3, 500, bedashing=True)
    cells = [_cell(C1, 1000), _cell(C2, 3000), _cell(C3, 2000), _cell(C5, 500), _cell(FAR, 4000, name="Far")]
    return _v3([a, b], cells, {"a": [C1, C2], "b": [C2, C3]}, [s1, bs],
               {"a": [s1, bs], "b": [s1, _salon("p-a", C1, 100, bedashing=True)]})


@pytest.fixture
def tiny_v3_empty():
    return _v3([_lounge("a", C1, 50, rating=None)], [_cell(C1, 1000)], {"a": [C1]}, [], {})


def women(v3, cid):
    return women_15plus(v3.cells, v3.emirates, ASSUMPTIONS.worker_housing_female_share["medium"])[cid]


@pytest.fixture(scope="module")
def real_v3():
    return load_v3()


def test_shared_share_counts_only_open_lounges(tiny_v3):
    f, _ = build(tiny_v3, ASSUMPTIONS)
    w = lambda c: women(tiny_v3, c)
    assert by_id(f)["a"].shared_share == pytest.approx(w(C2) / (w(C1) + w(C2)))
    assert by_id(f)["a"].catchment_women == pytest.approx(w(C1) + w(C2))
    f, _ = build(tiny_v3, ASSUMPTIONS, closed=frozenset({"b"}))
    assert by_id(f)["a"].shared_share == 0
    assert "b" not in by_id(f)


def test_closed_lounge_leaves_substitute_sets(tiny_v3):
    open_cap = by_id(build(tiny_v3, ASSUMPTIONS)[0])["a"].capture
    closed_cap = by_id(build(tiny_v3, ASSUMPTIONS, closed=frozenset({"b"}))[0])["a"].capture
    assert closed_cap > open_cap


def test_every_named_place_is_a_growth_area_reached_or_not(tiny_v3):
    # Served-demand model (2026-10-11): an area is any named place, inside a catchment or not; the
    # what-if (net new women) decides, not whether a lounge already reaches it. Closing changes nothing.
    for closed in (frozenset(), frozenset({"b"})):
        _, areas = build(tiny_v3, ASSUMPTIONS, closed=closed)
        assert {c for a in areas for c in a.cell_ids} == {C1, C2, C3, C5, FAR}


def test_one_growth_area_per_place_name_and_none_for_unnamed_cells(tiny_v3):
    _, areas = build(tiny_v3, ASSUMPTIONS, closed=frozenset({"b"}))
    town = [a for a in areas if a.name == "Town"]
    assert len(town) == 1 and set(town[0].cell_ids) == {C1, C2, C3, C5}   # not contiguous, one place: one area
    far = next(a for a in areas if a.name == "Far")
    assert far.area_id == "far-dubai" and far.nearest_lounge_id == "a"
    assert far.premium_salons is None and far.data_coverage == 0   # no search circle: no data
    # cells with only their emirate's name make no area, but still count in a lounge's catchment
    lone, inside = "r9c9", "r0c4"
    unnamed = [{**_cell(c, 3000, name="Dubai"), "name_source": "emirate"} for c in (lone, inside)]
    v = _v3(tiny_v3.lounges, [_cell(C1, 1000), _cell(C2, 3000), _cell(C3, 2000), *unnamed],
            {"a": [C1, C2, inside], "b": [C2, C3]}, [], {})
    f, areas = build(v, ASSUMPTIONS)
    assert all(lone not in x.cell_ids and inside not in x.cell_ids for x in areas)
    assert next(x for x in f if x.branch_id == "a").catchment_women == pytest.approx(
        women(v, C1) + women(v, C2) + women(v, inside))


def test_area_competition_over_covered_cells(tiny_v3):
    c = _cell(C1, 0)
    circle = {"purpose": "growth", "lat": c["lat"], "lng": c["lng"], "radius_m": 500, "results": 20, "full": True}
    v = _v3(tiny_v3.lounges, [_cell(C1, 1000), _cell(C2, 3000)], {"a": [], "b": []},
            [_salon("s1", C1, 300), _salon("p-a", C1, 100, bedashing=True)], {}, [circle])
    area = build(v, ASSUMPTIONS)[1][0]
    covered_women = women(v, C1)
    assert area.data_coverage == pytest.approx(covered_women / (covered_women + women(v, C2)))
    assert area.premium_salons == 1                       # s1; Bedashing's own is not competition
    assert area.full_circle_share == 1
    assert area.premium_reviews_per_1k == pytest.approx(300 / ASSUMPTIONS.search_recall / (covered_women / 1000))
    assert area.nearest_lounge_id == "a" and area.nearest_lounge_km < 2.5


def test_no_substitutes_and_no_ratings_never_nan(tiny_v3_empty):
    f = build(tiny_v3_empty, ASSUMPTIONS)[0][0]
    assert f.capture == 1.0 and f.thin_premium_market and f.rating_gap is None
    assert f.substitutes_k == 0 and f.premium_pool == 0 and f.est_customers == f.catchment_women


def test_airport_is_not_scored_and_out_of_every_comparison(real_v3):
    # Run-2 fix A1 (2026-10-10): the airport used to count as a sibling and a substitute (it decided
    # shahama's SHRINK) and its catchment blocked growth areas. Now it is in no comparison.
    from src.features.lounges import _candidates
    f, areas = build(real_v3, ASSUMPTIONS)
    air = by_id(f)["zayed-international-airport"]
    assert air.not_scored and air.est_customers == 0
    pid = next(lo.place_id for lo in real_v3.lounges if lo.branch_id == "zayed-international-airport")
    assert all(s["place_id"] != pid for lo in real_v3.lounges
               for s in _candidates(real_v3, Levels(), frozenset(), lo.branch_id))
    assert all(a.nearest_lounge_id != "zayed-international-airport" for a in areas)
    # shared_share: the same as with the airport closed, for every scored lounge
    closed = by_id(build(real_v3, ASSUMPTIONS, closed=frozenset({"zayed-international-airport"}), areas=False)[0])
    assert all(x.shared_share == closed[x.branch_id].shared_share for x in f if not x.not_scored)


def test_lounge_saturation_is_the_growth_area_measure(tiny_v3):
    # Run-2 fix B1: one helper for both (rubric MO8). Lounge a's catchment [C1] scored as a lounge
    # equals the growth area those same cells form once a is closed.
    c = _cell(C1, 0)
    circle = {"purpose": "growth", "lat": c["lat"], "lng": c["lng"], "radius_m": 500, "results": 20, "full": True}
    v = _v3([_lounge("a", C1, 100), _lounge("far", FAR, 10)], [_cell(C1, 1000), _cell(FAR, 0)],
            {"a": [C1], "far": []}, [_salon("s1", C1, 300), _salon("s2", C1, 50, price="moderate")], {}, [circle])
    lounge = by_id(build(v, ASSUMPTIONS)[0])["a"]
    area = build(v, ASSUMPTIONS, closed=frozenset({"a"}))[1][0]
    assert area.cell_ids == [C1]
    assert lounge.premium_reviews_per_1k == area.premium_reviews_per_1k == pytest.approx(
        300 / ASSUMPTIONS.search_recall / (women(v, C1) / 1000))


def test_every_level_combination_builds(real_v3):
    for lv in itertools.product(LEVELS, repeat=4):
        f, a = build(real_v3, ASSUMPTIONS, Levels(*lv))
        assert len(f) == 24 and all(x.catchment_women > 0 for x in f)
        assert a and all(x.women > 0 for x in a)
        assert len({x.area_id for x in a}) == len(a)       # Arabic-only names must not collide


def test_travel_level_changes_competition(real_v3):
    lo, hi = (by_id(build(real_v3, ASSUMPTIONS, Levels(travel=t))[0]) for t in ("low", "high"))
    assert all(hi[b].premium_pool >= lo[b].premium_pool for b in hi)
    assert any(hi[b].premium_pool > lo[b].premium_pool for b in hi)


def test_affluence_off_reproduces_the_unweighted_model_exactly(real_v3):
    from src.model import growth, scorecard
    off = Levels(affluence="low")
    f, areas = build(real_v3, ASSUMPTIONS, off)
    assert all(x.addressable_women == x.catchment_women for x in f)
    assert all(x.est_customers == (0.0 if x.not_scored else x.capture * x.catchment_women) for x in f)
    assert all(a.addressable_women == a.women for a in areas)
    # the calls are the baseline run's (affluence is off at baseline); no frozen composites since the
    # site-scored model (2026-10-11): calls are checked by behaviour, the call diff lives in SANITY_CHECKS
    from src.baseline import run
    r = run()
    assert [(d.branch_id, d.composite) for d in scorecard.decide(f)] == [(d.branch_id, d.composite) for d in r.decisions]
    assert [d.action for d in growth.classify_all(areas)] == [d.action for d in r.area_decisions]
    # and every number that doesn't read addressable women is untouched by the affluence level
    # (served-demand model: served women, the what-ifs and the cost index all read addressable women)
    med = build(real_v3, ASSUMPTIONS, Levels(affluence="medium"))
    keep = lambda x: x.model_dump(include={"catchment_women", "shared_share", "capture", "site_rent_m2", "site_cost_k"})
    assert [keep(x) for x in f] == [keep(x) for x in med[0]]
    # the what-if cache must tell levels apart: affluence keeps the demand total, so a key on the sum
    # collided and every level reused the first level's what-ifs (fixed 2026-10-11)
    awir = lambda xs: next(a for a in xs if a.area_id == "al-awir-dubai").new_site_net
    assert awir(areas) != awir(med[1])


def test_every_lounge_and_area_has_an_affluence_source(real_v3):
    f, areas = build(real_v3, ASSUMPTIONS)
    for x in [*f, *areas]:
        assert 0 <= x.affluence_coverage <= 1
        assert (x.affluence_rent is None) == (x.affluence_coverage == 0), x
    dubai = {x.branch_id: x for x in f if x.emirate == "Dubai"}
    assert all(x.affluence_coverage > 0.5 for x in dubai.values())
    assert all(x.affluence_rent is None and x.addressable_women == x.catchment_women
               for x in f if x.emirate in ("Abu Dhabi", "Ras Al Khaimah"))


def test_a_better_rated_competitor_never_raises_a_lounge(real_v3):
    # Sanity check SC4, run 2: one 4.9-star salon added to al-maqta's pool raised it SHRINK -> HOLD,
    # because the rating median ran over a top-k whose k grew with the pool.
    from src.features import lounges
    from src.model import scorecard
    b, travel = "al-maqta", Levels().travel
    base = {d.branch_id: d.composite for d in scorecard.decide(build(real_v3, ASSUMPTIONS)[0])}
    rival = {"place_id": "test-rival", "name": "Test rival", "rating": 4.9, "review_count": 259,
             "price_level": "", "lat": 0.0, "lng": 0.0}
    real_v3.candidates[(b, travel)].append(rival)
    lounges._PREP.clear()
    try:
        after = {d.branch_id: d.composite for d in scorecard.decide(build(real_v3, ASSUMPTIONS)[0])}
    finally:
        real_v3.candidates[(b, travel)].remove(rival)
    assert after[b] <= base[b]


def test_women_per_rent_is_none_without_rent_and_scales_with_rent():
    from src.features.lounges import REF_UNIT_M2, women_per_rent_k
    assert women_per_rent_k(50_000, None) is None
    assert women_per_rent_k(50_000, float("nan")) is None
    assert women_per_rent_k(50_000, 2000.0) == pytest.approx(50_000 / (2000 * REF_UNIT_M2 / 1000))
    assert women_per_rent_k(50_000, 1000.0) == pytest.approx(2 * women_per_rent_k(50_000, 2000.0))


def test_shop_rent_is_women_weighted_over_cells_that_have_one(tiny_v3):
    tiny_v3.cells["shop_rent_m2"] = float("nan")
    tiny_v3.cells.loc[C1, "shop_rent_m2"] = 1000.0
    tiny_v3.cells.loc[C2, "shop_rent_m2"] = 3000.0
    tiny_v3.cells["shop_rent_source"] = tiny_v3.cells.shop_rent_m2.map(lambda x: "none" if x != x else "dld")
    f, _ = build(tiny_v3, ASSUMPTIONS)
    a = next(x for x in f if x.branch_id == "a")            # reaches C1 (1000 adults), C2 (3000)
    assert a.catchment_shop_rent_m2 == 3000.0                # women-weighted median: C2 holds the majority
    assert a.shop_rent_coverage == pytest.approx(1.0)
    assert a.site_rent_m2 == 1000.0 and a.site_rent_source == "dld"   # a sits in C1
    b = next(x for x in f if x.branch_id == "b")            # sits in C3: no shop rent there
    assert b.site_rent_m2 is None and b.site_rent_source == "none" and b.women_per_rent_k is None


def test_every_scored_lounge_has_a_site_rent_from_its_cell(real_v3):
    # Since 2026-10-11 every cell has a shop rent (DLD, ADREC, listings or the emirate median); the
    # JLL mall-class bands are no longer used, and a lounge's site rent is its cell's.
    f, _ = build(real_v3, ASSUMPTIONS)
    for x in f:
        assert x.site_rent_m2 and x.site_rent_source in ("dld", "adrec", "listings", "emirate_median"), x.branch_id
    assert {x.site_rent_source for x in f if x.emirate == "Dubai"} == {"dld"}


def test_signals_rank_the_site_in_the_frozen_salon_site_reference(real_v3):
    # Owner's call (2026-10-11): judge each site within its emirate's market of salon SITES, never
    # against our own lounges; under MIN_REF_SITES the demand ranks UAE-wide.
    import numpy as np

    from src.features.lounges import MIN_REF_SITES, site_reference
    from src.model.scorecard import RENT_RATIO_P10, RENT_RATIO_P90
    ref = site_reference()
    n = ref.emirate.value_counts()
    med = ref.groupby("emirate").shop_rent_m2.median()
    f, areas = build(real_v3, ASSUMPTIONS)
    for x in (x for x in f if not x.not_scored):
        own = n.get(x.emirate, 0) >= MIN_REF_SITES
        pool = ref[ref.emirate == x.emirate] if own else ref
        assert x.demand_ref == (x.emirate if own else "UAE")
        assert x.demand_pct == pytest.approx((pool.ref_served < x.site_served).mean()), x.branch_id
        assert x.demand_pct_uae == pytest.approx((ref.ref_served < x.site_served).mean())
        assert x.rent_ratio == pytest.approx(med[x.emirate] / x.site_rent_m2)
        assert x.rent_pct_uae == pytest.approx((ref.shop_rent_m2 < x.site_rent_m2).mean())
    for a in (a for a in areas if a.new_site_served is not None):
        assert a.demand_pct_uae == pytest.approx((ref.ref_served < a.new_site_served).mean()), a.area_id
    assert {x.demand_ref for x in f if x.emirate in ("Fujairah", "Ras Al Khaimah")} == {"UAE"}
    # the rent scale is the frozen P10 / P90 of every reference site against its own emirate's median
    ratio = ref.emirate.map(med) / ref.shop_rent_m2
    assert (RENT_RATIO_P10, RENT_RATIO_P90) == pytest.approx(tuple(np.percentile(ratio, [10, 90])), abs=1e-4)


def test_closing_a_lounge_never_moves_another_lounges_reference(real_v3, monkeypatch):
    # Frozen reference: closing any lounge never changes another lounge's rent ratio or the salon sites
    # its demand is ranked against; its demand percentile moves only with its own site-served women.
    # Frozen typical lounge (TYPICAL_WHY): every closure's site_served opens the same 757-review 4.6 lounge,
    # so no closure moves another lounge's call through the typical lounge (khaleej-al-arabi drifted before).
    from src.features import lounges
    from src.model import served
    typicals = set()
    real_site_served = served.site_served

    def spy(v3, a, aw, reviews, rating, **kw):
        typicals.add((reviews, rating))
        return real_site_served(v3, a, aw, reviews, rating, **kw)
    monkeypatch.setattr(served, "site_served", spy)
    monkeypatch.setattr(lounges, "_SERVED", {k: v for k, v in lounges._SERVED.items() if k[0] != "site"})
    ref = lounges.site_reference().copy()
    base = {x.branch_id: x for x in build(real_v3, ASSUMPTIONS, areas=False)[0] if not x.not_scored}
    for gone in base:
        for x in build(real_v3, ASSUMPTIONS, closed=frozenset({gone}), areas=False)[0]:
            if x.not_scored:
                continue
            b = base[x.branch_id]
            assert (x.rent_ratio, x.rent_pct_uae, x.demand_ref) == (b.rent_ratio, b.rent_pct_uae, b.demand_ref)
            same = lounges.site_signals(x.emirate, x.site_served, x.site_rent_m2)
            assert (x.demand_pct, x.demand_pct_uae) == (same["demand_pct"], same["demand_pct_uae"]), (gone, x.branch_id)
    assert lounges.site_reference().equals(ref)
    assert typicals == {(lounges.TYPICAL_REVIEWS, lounges.TYPICAL_RATING)}


def test_typical_lounge_is_frozen_at_the_baseline_median():
    # the frozen values are today's all-open medians, and the ones the salon-site reference was built with
    import statistics

    from src.data_v3 import load_v3
    from src.features import lounges
    scored = [lo for lo in load_v3().lounges if lo.branch_id not in lounges.NOT_SCORED]
    assert statistics.median(lo.review_count for lo in scored) == lounges.TYPICAL_REVIEWS
    assert statistics.median(lo.rating for lo in scored if lo.rating is not None) == lounges.TYPICAL_RATING
    head = lounges.SITE_REFERENCE.read_text().splitlines()[0]
    assert f"typical lounge {lounges.TYPICAL_REVIEWS} reviews, {lounges.TYPICAL_RATING} stars" in head


def test_site_served_is_a_typical_lounge_at_the_site_with_this_one_closed(real_v3):
    # F2 (2026-10-11): the demand signal scores the site, not the lounge's own reviews
    from src.features.lounges import NOT_SCORED, TYPICAL_RATING, TYPICAL_REVIEWS, _SERVED
    from src.market import affluence_weight, women_15plus
    from src.model.served import what_if_open
    f, _ = build(real_v3, ASSUMPTIONS, areas=False)
    scored = [x for x in f if not x.not_scored]
    reviews, rating = TYPICAL_REVIEWS, TYPICAL_RATING
    a, lv = ASSUMPTIONS, Levels()
    women = women_15plus(real_v3.cells, real_v3.emirates, a.worker_housing_female_share[lv.worker_share])
    demand = women * affluence_weight(real_v3.cells.rent_observed, women, a.affluence_elasticity[lv.affluence])
    for x in scored[:3]:
        w = what_if_open(real_v3, a, demand, x.lat, x.lng, reviews, rating, closed=frozenset({x.branch_id}),
                         not_scored=frozenset(NOT_SCORED))
        assert x.site_served == pytest.approx(w["served"])
        assert x.performance_vs_site == pytest.approx(x.served_women / x.site_served)
    assert _SERVED   # cached: level_flips' 81 builds reuse it
    air = next(x for x in f if x.not_scored)
    assert air.site_served is None and air.performance_vs_site is None


def test_shop_rent_needs_half_the_women_covered(tiny_v3):
    # Review I4: an area rent standing on cells with 10% of its women is not the area's rent.
    from src.features.lounges import _shop_rent
    w = {"x": 100.0, "y": 900.0}
    assert _shop_rent(["x", "y"], w, {"x": 2000.0}) == (None, pytest.approx(0.1))
    assert _shop_rent(["x", "y"], w, {"y": 2000.0}) == (2000.0, pytest.approx(0.9))
