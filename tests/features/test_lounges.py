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


def test_cells_only_a_closed_lounge_reached_become_growth_areas(tiny_v3):
    _, areas = build(tiny_v3, ASSUMPTIONS)
    assert {c for a in areas for c in a.cell_ids} == {C5, FAR}
    _, areas = build(tiny_v3, ASSUMPTIONS, closed=frozenset({"b"}))
    cells = {c for a in areas for c in a.cell_ids}
    assert C3 in cells and C2 not in cells          # C2 is still a's


def test_growth_areas_split_into_connected_pieces(tiny_v3):
    _, areas = build(tiny_v3, ASSUMPTIONS, closed=frozenset({"b"}))
    town = [a for a in areas if a.name == "Town"]
    assert [(a.area_id, a.cell_ids) for a in town] == [("town-dubai", [C3]), ("town-dubai-2", [C5])]
    far = next(a for a in areas if a.name == "Far")
    assert far.area_id == "far-dubai" and far.nearest_lounge_id == "a"
    assert far.premium_salons is None and far.data_coverage == 0   # no search circle: no data


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


# Composites and GROW areas at medium levels before affluence existed (commit f049b9b), updated for
# the run-2 fixes (2026-10-10): A1 (airport out of shared catchments and substitute pools) moved
# al-maqta, khalifa-city-a, ministries-complex, noya-plaza, shahama and westyas; A4 (thin-market
# blend) moved al-dhafra 0.4851 -> 0.5851 and al-falah 0.4809 -> 0.5666; D1 (saturation line 50 ->
# 150) added al-jerf-ajman to GROW. Affluence off must still reproduce the unweighted model.
BEFORE_AFFLUENCE = {
    "al-ain": 0.7619, "al-barsha": 0.3664, "al-dhafra": 0.5851, "al-falah": 0.5666, "al-jada": 0.4872,
    "al-maqta": 0.3411, "al-taif-mall": 0.6933, "baniyas": 0.4224, "city-walk": 0.4074, "delma": 0.227,
    "jumeirah-park": 0.4132, "khaleej-al-arabi": 0.2773, "khalifa-city-a": 0.4255,
    "ministries-complex": 0.3831, "mirdif-35": 0.4974, "mohammed-bin-zayed-city": 0.2769,
    "nad-al-sheba": 0.4345, "noya-plaza": 0.2156, "ras-al-khaimah": 0.6643, "shahama": 0.3828,
    "shakhbout-city": 0.4194, "westyas": 0.2252, "zawaya-walk": 0.5135}
GROW_BEFORE = {"sharjah-sharjah", "al-dhaid-sharjah", "khor-fakkan-sharjah", "kalba-sharjah", "al-jerf-ajman"}


def test_affluence_off_reproduces_the_unweighted_model_exactly(real_v3):
    from src.model import growth, scorecard
    off = Levels(affluence="low")
    f, areas = build(real_v3, ASSUMPTIONS, off)
    assert all(x.addressable_women == x.catchment_women for x in f)
    assert all(x.est_customers == (0.0 if x.not_scored else x.capture * x.catchment_women) for x in f)
    assert all(a.addressable_women == a.women for a in areas)
    got = {d.branch_id: d.composite for d in scorecard.decide(f) if d.action != "NOT SCORED"}
    assert got == BEFORE_AFFLUENCE
    assert {d.area_id for d in growth.classify_all(areas) if d.action == "GROW"} == GROW_BEFORE
    # and every other number is untouched by the affluence level
    med = build(real_v3, ASSUMPTIONS)
    strip = lambda x: x.model_dump(exclude={"addressable_women", "est_customers"})
    assert [strip(x) for x in f] == [strip(x) for x in med[0]]
    assert [strip(x) for x in areas] == [strip(x) for x in med[1]]


def test_every_lounge_and_area_has_an_affluence_source(real_v3):
    f, areas = build(real_v3, ASSUMPTIONS)
    for x in [*f, *areas]:
        assert 0 <= x.affluence_coverage <= 1
        assert (x.affluence_rent is None) == (x.affluence_coverage == 0), x
    dubai = {x.branch_id: x for x in f if x.emirate == "Dubai"}
    assert all(x.affluence_coverage > 0.5 for x in dubai.values())
    assert all(x.affluence_rent is None and x.addressable_women == x.catchment_women
               for x in f if x.emirate in ("Abu Dhabi", "Ras Al Khaimah"))
