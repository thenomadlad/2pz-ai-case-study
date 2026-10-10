import pytest

from src.features.lounges import build
from src.model.growth import (
    GROW_MIN_WOMEN,
    MIN_COVERAGE,
    SKIP_UNDER_WOMEN,
    UNSATURATED_PER_1K,
    WORKER_CAP,
    classify,
)
from src.models import Area
from tests.features.test_lounges import ASSUMPTIONS, C1, C2, _cell, _lounge, _salon, _v3, women


def _a(women=50_000.0, worker=0.1, per_1k=0.0, coverage=1.0, addressable=None):
    return Area(area_id="x", name="X", emirate="Dubai", lat=25, lng=55, women=women,
                addressable_women=women if addressable is None else addressable,
                affluence_rent=None, affluence_coverage=0.0, cells=3,
                worker_share=worker, premium_salons=None if per_1k is None else 1,
                premium_reviews_per_1k=per_1k, full_circle_share=None if per_1k is None else 0.5,
                data_coverage=0.0 if per_1k is None else coverage, cell_ids=["r0c0"],
                nearest_lounge_id="al-barsha", nearest_lounge_km=12.3)


def test_constants():
    assert (GROW_MIN_WOMEN, SKIP_UNDER_WOMEN, WORKER_CAP, MIN_COVERAGE) == (20_000, 5_000, 0.5, 0.5)
    assert UNSATURATED_PER_1K > 0


def test_grow_watch_skip_on_the_two_questions():
    low, high = UNSATURATED_PER_1K * 0.99, UNSATURATED_PER_1K
    assert classify(_a(women=GROW_MIN_WOMEN, per_1k=low)).action == "GROW"
    d = classify(_a(women=GROW_MIN_WOMEN, per_1k=high))
    assert (d.action, d.big_enough, d.unsaturated) == ("WATCH", True, False)
    d = classify(_a(women=GROW_MIN_WOMEN - 1, per_1k=low))
    assert (d.action, d.big_enough, d.unsaturated) == ("WATCH", False, True)
    assert classify(_a(women=GROW_MIN_WOMEN - 1, per_1k=high)).action == "SKIP"
    assert classify(_a(women=SKIP_UNDER_WOMEN - 1, per_1k=low)).action == "SKIP"


def test_worker_housing_caps_at_watch():
    d = classify(_a(worker=WORKER_CAP, per_1k=0))
    assert d.action == "WATCH" and not d.big_enough and "worker" in d.rationale
    assert classify(_a(worker=WORKER_CAP - 0.01, per_1k=0)).action == "GROW"


def test_no_competitor_data_is_unknown_and_at_most_watch():
    d = classify(_a(per_1k=None))
    assert d.unsaturated is None and d.action == "WATCH"
    assert any("no competitor data" in c.lower() for c in d.caveats)
    assert classify(_a(women=10_000, per_1k=None)).action == "SKIP"


def test_low_coverage_cannot_grow():
    d = classify(_a(per_1k=0, coverage=MIN_COVERAGE - 0.01))
    assert d.action == "WATCH" and d.unsaturated is True
    assert classify(_a(per_1k=0, coverage=MIN_COVERAGE)).action == "GROW"


def test_rationale_shows_nearest_lounge():
    assert "al-barsha" in classify(_a()).rationale and "12.3 km" in classify(_a()).rationale


def test_mixed_area_saturation_ignores_uncovered_cells():
    c = _cell(C1, 0)
    circle = {"purpose": "growth", "lat": c["lat"], "lng": c["lng"], "radius_m": 500, "results": 20, "full": True}
    lo = _lounge("far", "r9c9", 10)

    def area(uncovered_adults):
        v = _v3([lo], [_cell(C1, 100_000), _cell(C2, uncovered_adults), _cell("r9c9", 0)], {"far": []},
                [_salon("s1", C1, 300)], {}, [circle])
        return v, build(v, ASSUMPTIONS)[1][0]

    v, small = area(1_000)
    _, big = area(1_000_000)
    assert small.premium_reviews_per_1k == pytest.approx(big.premium_reviews_per_1k)
    assert big.data_coverage < MIN_COVERAGE and small.data_coverage > MIN_COVERAGE
    assert classify(big).action != "GROW"
    assert small.premium_reviews_per_1k == pytest.approx(300 / ASSUMPTIONS.search_recall / (women(v, C1) / 1000))


def test_airport_catchment_still_blocks_growth_areas():
    air = _lounge("zayed-international-airport", C1, 10)
    v = _v3([air], [_cell(C1, 100_000), _cell(C2, 100_000)], {"zayed-international-airport": [C1]}, [], {})
    _, areas = build(v, ASSUMPTIONS)
    assert [a.cell_ids for a in areas] == [[C2]]
