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


def test_airport_catchment_is_open_to_growth_areas():
    # Run-2 fix A1 (2026-10-10) reverses the old rule (its catchment blocked growth areas): the
    # airport lounge serves travellers, so the women around it are not served. Not its nearest lounge either.
    air, other = _lounge("zayed-international-airport", C1, 10), _lounge("b", "r9c9", 10)
    v = _v3([air, other], [_cell(C1, 100_000), _cell(C2, 100_000), _cell("r9c9", 0)],
            {"zayed-international-airport": [C1], "b": []}, [], {})
    _, areas = build(v, ASSUMPTIONS)
    assert [a.cell_ids for a in areas] == [[C1, C2]] and areas[0].nearest_lounge_id == "b"


def test_small_unsaturated_worker_housing_is_skip():
    # Run-2 fix A2: the small-and-unsaturated WATCH branch never applied WORKER_CAP (BT4: JAFZ North WATCH).
    small = {"women": GROW_MIN_WOMEN - 1, "per_1k": 0}
    assert classify(_a(worker=WORKER_CAP - 0.01, **small)).action == "WATCH"
    d = classify(_a(worker=WORKER_CAP, **small))
    assert d.action == "SKIP" and "worker housing" in d.rationale


@pytest.mark.parametrize(("name", "skip"), [
    ("Jebel Ali North Free Zone", True), ("Al Qusais Industrial Area", True), ("Zayed Military City", True),
    ("Sharjah International Airport", True), ("Jebel Ali Port", True), ("المنطقة الصناعية", True),
    ("Port Saeed", False), ("Mina Al arab", False), ("Dubai Investments Park", False), ("Airportside", False)])
def test_non_residential_names_skip_before_any_test(name, skip):
    # Run-2 fix A3. A GROW-sized, empty area: only the name can make it SKIP.
    d = classify(_a(per_1k=0).model_copy(update={"name": name}))
    assert (d.action == "SKIP") == skip and (("Non-residential" in d.rationale) == skip)


def test_saturation_line_is_the_p25_of_working_lounge_catchments():
    # Run-2 fix D1(a): the rule fixed in advance, recomputed at baseline levels.
    import numpy as np

    from src.data_v3 import load_v3
    from src.model.scorecard import THIN_MARKET
    f, _ = build(load_v3(), ASSUMPTIONS)
    per_1k = [x.premium_reviews_per_1k for x in f if x.premium_pool >= THIN_MARKET and not x.not_scored]
    assert len(per_1k) == 21
    assert round(float(np.percentile(per_1k, 25)), -1) == UNSATURATED_PER_1K


def test_area_confidence():
    # Run-2 fix B2: low near a line or on missing / thin data, high 20%+ from both lines.
    assert classify(_a(women=50_000, per_1k=0)).confidence == "high"
    assert classify(_a(women=GROW_MIN_WOMEN * 1.15, per_1k=0)).confidence == "medium"
    d = classify(_a(women=GROW_MIN_WOMEN * 1.05, per_1k=0))
    assert d.confidence == "low" and any("size line" in c for c in d.caveats)
    d = classify(_a(per_1k=UNSATURATED_PER_1K * 0.95))
    assert d.confidence == "low" and any("saturation line" in c for c in d.caveats)
    assert classify(_a(per_1k=None)).confidence == "low"
    assert classify(_a(per_1k=0, coverage=MIN_COVERAGE - 0.01)).confidence == "low"


def test_size_passed_only_through_thin_affluence_data_caps_at_watch():
    thin = _a(women=GROW_MIN_WOMEN - 1, addressable=GROW_MIN_WOMEN, per_1k=0)
    thin = thin.model_copy(update={"affluence_coverage": MIN_COVERAGE - 0.01})
    d = classify(thin)
    assert d.action == "WATCH" and d.big_enough and "affluence weighting" in d.rationale
    assert any("Affluence data covers only 49%" in c and "19,999 women before weighting" in c for c in d.caveats)
    assert classify(thin.model_copy(update={"affluence_coverage": MIN_COVERAGE})).action == "GROW"
    # raw women already over the line: the weighting isn't what passes it
    assert classify(_a(women=GROW_MIN_WOMEN, addressable=GROW_MIN_WOMEN + 5, per_1k=0)).action == "GROW"
