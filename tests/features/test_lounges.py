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
            "adults": adults, "adults_worker": 0}


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


def test_airport_is_not_scored_but_still_reaches(real_v3):
    f, areas = build(real_v3, ASSUMPTIONS)
    air = by_id(f)["zayed-international-airport"]
    assert air.not_scored and air.est_customers == 0
    reached = set(real_v3.catchment.query("level == 'medium' and branch_id == 'zayed-international-airport'").cell_id)
    assert not reached & {c for a in areas for c in a.cell_ids}


def test_every_level_combination_builds(real_v3):
    for t, c, w in itertools.product(LEVELS, repeat=3):
        f, a = build(real_v3, ASSUMPTIONS, Levels(t, c, w))
        assert len(f) == 24 and all(x.catchment_women > 0 for x in f)
        assert a and all(x.women > 0 for x in a)


def test_travel_level_changes_competition(real_v3):
    lo, hi = (by_id(build(real_v3, ASSUMPTIONS, Levels(travel=t))[0]) for t in ("low", "high"))
    assert all(hi[b].premium_pool >= lo[b].premium_pool for b in hi)
    assert any(hi[b].premium_pool > lo[b].premium_pool for b in hi)
