import pytest

from src.features.lounges import build
from src.model.growth import (
    DEMAND_PCT_MIN,
    MIN_COVERAGE,
    NEW_SITE_MIN,
    RENT_FALLBACK_MIN,
    RENT_RATIO_MIN,
    SKIP_UNDER_WOMEN,
    UNSATURATED_PER_1K,
    WORKER_CAP,
    classify,
)
from src.models import Area
from tests.features.test_lounges import ASSUMPTIONS, C1, C2, _cell, _lounge, _salon, _v3, women


# Served-demand model 2026-10-11: an area's call comes from the open-a-lounge what-if (net new women
# >= NEW_SITE_MIN), its demand percentile and rent ratio against the frozen salon-site reference.
def _a(women=50_000.0, worker=0.1, per_1k=0.0, coverage=1.0, net=10_000.0, rent=None, demand=None, ref="Dubai"):
    return Area(area_id="x", name="X", emirate="Dubai", lat=25, lng=55, women=women, addressable_women=women,
                affluence_rent=None, affluence_coverage=0.0, cells=3,
                worker_share=worker, premium_salons=None if per_1k is None else 1,
                premium_reviews_per_1k=per_1k, full_circle_share=None if per_1k is None else 0.5,
                data_coverage=0.0 if per_1k is None else coverage, cell_ids=["r0c0"],
                nearest_lounge_id="al-barsha", nearest_lounge_km=12.3, new_site_net=net, rent_ratio=rent,
                demand_pct=demand, demand_pct_uae=demand, rent_pct_uae=None if rent is None else 0.5, demand_ref=ref)


def test_constants():
    assert (SKIP_UNDER_WOMEN, WORKER_CAP, MIN_COVERAGE, NEW_SITE_MIN) == (5_000, 0.5, 0.5, 6_000)


def test_grow_watch_skip_on_net_new_women_rent_and_demand():
    assert classify(_a(net=NEW_SITE_MIN)).action == "GROW"
    d = classify(_a(net=NEW_SITE_MIN, rent=RENT_RATIO_MIN, demand=DEMAND_PCT_MIN))
    assert d.action == "GROW" and "top 50% of Dubai salon sites on demand" in d.rationale
    d = classify(_a(net=NEW_SITE_MIN, rent=0.99, demand=0.9))
    assert d.action == "WATCH" and "more expensive" in d.rationale and "weaker" not in d.rationale
    d = classify(_a(net=NEW_SITE_MIN, rent=1.2, demand=0.49))
    assert d.action == "WATCH" and "weaker demand" in d.rationale and "more expensive" not in d.rationale
    assert "UAE-wide" in d.rationale                                       # the UAE context, always
    assert classify(_a(net=NEW_SITE_MIN - 1)).action == "WATCH"           # half a lounge or more
    assert classify(_a(net=NEW_SITE_MIN / 2 - 1)).action == "SKIP"
    assert classify(_a(women=SKIP_UNDER_WOMEN - 1, net=50_000)).action == "SKIP"


def test_worker_housing_caps_at_watch():
    d = classify(_a(worker=WORKER_CAP))
    assert d.action == "WATCH" and not d.big_enough and "worker" in d.rationale
    assert classify(_a(worker=WORKER_CAP - 0.01)).action == "GROW"


def test_unknown_rent_is_a_caveat_not_a_block():
    d = classify(_a(rent=None, demand=0.8))
    assert d.action == "GROW" and any("rent unknown" in c for c in d.caveats)


def test_fallback_rent_is_neutral_and_low_confidence():
    # growth.RENT_FALLBACK_WHY: half or more of the rented women on the emirate median -> the test passes
    fb = _a(net=20_000, rent=0.9, demand=0.9, per_1k=0.0).model_copy(update={"shop_rent_fallback_share": RENT_FALLBACK_MIN})
    d = classify(fb)
    assert d.action == "GROW" and d.confidence == "low" and any("median, not observed" in c for c in d.caveats)
    assert "neutral" in d.rationale
    observed = fb.model_copy(update={"shop_rent_fallback_share": RENT_FALLBACK_MIN - 0.01})
    assert classify(observed).action == "WATCH"


def test_small_emirates_rank_demand_uae_wide_and_say_so():
    d = classify(_a(rent=1.1, demand=0.8, ref="UAE").model_copy(update={"emirate": "Fujairah"}))
    assert "UAE salon sites (Fujairah has under 50)" in d.rationale
    assert any("ranked UAE-wide" in c for c in d.caveats)


def test_low_coverage_is_low_confidence_with_a_caveat():
    d = classify(_a(coverage=MIN_COVERAGE - 0.01))
    assert d.confidence == "low" and any("imputed" in c for c in d.caveats)


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
    assert small.premium_reviews_per_1k == pytest.approx(300 / ASSUMPTIONS.search_recall / (women(v, C1) / 1000))


def test_airport_catchment_is_open_to_growth_areas():
    # Run-2 fix A1 (2026-10-10) reverses the old rule (its catchment blocked growth areas): the
    # airport lounge serves travellers, so the women around it are not served. Not its nearest lounge either.
    air, other = _lounge("zayed-international-airport", C1, 10), _lounge("b", "r9c9", 10)
    v = _v3([air, other], [_cell(C1, 100_000), _cell(C2, 100_000), _cell("r9c9", 0)],
            {"zayed-international-airport": [C1], "b": []}, [], {})
    _, areas = build(v, ASSUMPTIONS)
    assert [a.cell_ids for a in areas] == [[C1, C2]] and areas[0].nearest_lounge_id == "b"


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
    # Within 10% of NEW_SITE_MIN or on mostly imputed competitors: low; 20%+ away: high.
    assert classify(_a(net=NEW_SITE_MIN * 1.5)).confidence == "high"
    assert classify(_a(net=NEW_SITE_MIN * 1.15)).confidence == "medium"
    assert classify(_a(net=NEW_SITE_MIN * 1.05)).confidence == "low"
