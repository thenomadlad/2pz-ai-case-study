import pytest

from src.model.rubric import RubricModel
from src.models import BranchFeatures, NetworkStats


def _features(branch_id, pop, contested_share, rating):
    return BranchFeatures(
        branch_id=branch_id, name=branch_id, lat=25.0, lng=55.0,
        female_pop_served=pop, communities_served=1, mean_distance_km=1.0, max_distance_km=1.0,
        contested_pop=0, contested_share=contested_share, nearest_sibling_km=5.0,
        siblings_within_5km=0, avg_price_aed=100.0, price_index=1.0, rating=rating,
        review_count=10, pop_per_1k_rank=0, estimated_fields=[],
    )


NETWORK = NetworkStats(
    branch_count=3, total_female_population=6000,
    female_pop_served_median=2000, female_pop_served_p25=1500, female_pop_served_p75=2500,
    contested_share_median=0.2, contested_share_p25=0.1, contested_share_p75=0.3,
    avg_price_aed_median=100, avg_price_aed_p25=90, avg_price_aed_p75=110,
    rating_median=4.3, rating_p25=4.0, rating_p75=4.6,
)


def test_rubric_ranks_top_and_bottom_thirds():
    branches = [
        _features("strong", pop=5000, contested_share=0.05, rating=4.9),
        _features("mid", pop=2000, contested_share=0.2, rating=4.3),
        _features("weak", pop=500, contested_share=0.6, rating=3.5),
    ]

    decisions = RubricModel().decide(branches, NETWORK)
    by_id = {d.branch_id: d for d in decisions}

    assert by_id["strong"].action == "PROTECT"
    assert by_id["weak"].action == "SHRINK"
    assert all(d.confidence == "medium" for d in decisions)
    assert all(len(d.key_drivers) == 2 for d in decisions)


def test_rubric_decide_empty_branch_list_returns_empty_without_crashing():
    # min()/max() on the empty `pops`/`contested`/`ratings` lists would otherwise raise
    # ValueError. RubricModel.decide([]) is explicitly supported and returns [] early.
    assert RubricModel().decide([], NETWORK) == []


def test_rubric_handles_missing_rating():
    branches = [
        _features("a", pop=3000, contested_share=0.1, rating=None),
        _features("b", pop=1000, contested_share=0.5, rating=None),
    ]
    decisions = RubricModel().decide(branches, NETWORK)
    assert len(decisions) == 2


def _composite_from_rationale(decision) -> float:
    # Rationale text is "Composite rubric score {composite:.2f} on population, ..."
    marker = "Composite rubric score "
    start = decision.rationale.index(marker) + len(marker)
    return float(decision.rationale[start:start + 4])


def test_rubric_uses_hardcoded_fallback_when_no_network_rating():
    # NetworkStats with all rating fields None to exercise the 4.0 hardcoded fallback
    # in src/model/rubric.py: `rating_fallback = network.rating_median if ... else 4.0`.
    #
    # Batch is a MIXED batch (not all-None like the previous version of this test):
    #   "low"  has a real rating=3.0
    #   "high" has a real rating=4.0
    #   "none" has rating=None, so its rating is filled in with rating_fallback
    #
    # Because "low" and "high" both carry real ratings, `ratings` is non-empty, so
    # rating_lo, rating_hi = (3.0, 4.0) -- a genuine, non-degenerate range (unlike the
    # old test, where every branch had rating=None, ratings=[] forced
    # rating_lo == rating_hi == rating_fallback, and _normalize's `if hi == lo: return
    # 0.5` guard swallowed the fallback's value entirely before it could affect anything).
    #
    # population and contested_share are identical across all three branches, so
    # pop_score and contest_score are 0.5 for every branch (their own hi==lo guard
    # fires) -- this isolates the rating dimension as the *only* source of composite
    # score differences.
    #
    # Hand computation:
    #   pop_score = contest_score = 0.5 for all three branches (identical inputs)
    #   "low":  rating_score = _normalize(3.0, 3.0, 4.0) = 0.0
    #           composite   = (0.5 + 0.5 + 0.0) / 3 = 0.333... -> "0.33"
    #   "high": rating_score = _normalize(4.0, 3.0, 4.0) = 1.0
    #           composite   = (0.5 + 0.5 + 1.0) / 3 = 0.666... -> "0.67"
    #   "none": rating_value = rating_fallback = 4.0 (network.rating_median is None)
    #           rating_score = _normalize(4.0, 3.0, 4.0) = 1.0   <- same as "high"
    #           composite   = (0.5 + 0.5 + 1.0) / 3 = 0.666... -> "0.67"
    #
    # If the hardcoded fallback were changed from 4.0 to, say, 3.0, "none" would
    # instead compute rating_score = _normalize(3.0, 3.0, 4.0) = 0.0, matching "low"
    # (composite "0.33") instead of "high" -- a change this test would catch by
    # comparing composites and actions.
    network_no_rating = NetworkStats(
        branch_count=3, total_female_population=6000,
        female_pop_served_median=2000, female_pop_served_p25=1500, female_pop_served_p75=2500,
        contested_share_median=0.2, contested_share_p25=0.1, contested_share_p75=0.3,
        avg_price_aed_median=100, avg_price_aed_p25=90, avg_price_aed_p75=110,
        rating_median=None, rating_p25=None, rating_p75=None,
    )
    branches = [
        _features("low", pop=2000, contested_share=0.2, rating=3.0),
        _features("high", pop=2000, contested_share=0.2, rating=4.0),
        _features("none", pop=2000, contested_share=0.2, rating=None),
    ]
    decisions = RubricModel().decide(branches, network_no_rating)
    by_id = {d.branch_id: d for d in decisions}
    assert len(decisions) == 3

    low_composite = _composite_from_rationale(by_id["low"])
    high_composite = _composite_from_rationale(by_id["high"])
    none_composite = _composite_from_rationale(by_id["none"])

    # The None-rating branch scores identically to the branch with a *real* 4.0
    # rating, and strictly higher than the branch with a real 3.0 rating -- this
    # is only true because the fallback resolves to 4.0.
    assert none_composite == pytest.approx(0.67, abs=0.005)
    assert none_composite == pytest.approx(high_composite, abs=1e-9)
    assert none_composite > low_composite
    assert low_composite == pytest.approx(0.33, abs=0.005)

    # Ranking-level confirmation: "none" lands in the same non-bottom tier as "high",
    # not lumped in with "low" at the bottom.
    assert by_id["high"].action == "PROTECT"
    assert by_id["none"].action == "HOLD"
    assert by_id["low"].action == "SHRINK"


def test_key_drivers_normalizes_deviation_by_iqr_not_raw_magnitude():
    # NETWORK IQRs: female_pop_served=1000 (2500-1500), contested_share=0.2 (0.3-0.1),
    # rating=0.6 (4.6-4.0).
    #
    # Branch deviations from network medians:
    #   female_pop_served: |2200 - 2000| = 200   -> raw deviation is huge in absolute terms
    #   contested_share:   |0.05 - 0.2|  = 0.15
    #   rating:             |4.8 - 4.3|  = 0.5
    #
    # Raw (unnormalized) ranking by absolute deviation: population (200) >> rating (0.5) >
    # contested_share (0.15). The old, buggy code would pick {female_pop_served, rating} as
    # key drivers every time, because population deviates by ~10^2-10^3 in absolute terms
    # while the other two features live in [0, 1]-ish ranges -- population wins purely on
    # scale, not because it's actually the most unusual feature for this branch.
    #
    # Normalized-by-IQR ranking: population 200/1000=0.20, contested_share 0.15/0.2=0.75,
    # rating 0.5/0.6=0.833. So rating and contested_share are actually the two most unusual
    # features (in IQR-relative terms) for this branch, and population -- despite its huge
    # raw deviation -- is actually the *least* unusual once you account for scale.
    branch = _features("scale-test", pop=2200, contested_share=0.05, rating=4.8)

    decisions = RubricModel().decide([branch], NETWORK)
    key_drivers = set(decisions[0].key_drivers)

    assert key_drivers == {"rating", "contested_share"}
    assert "female_pop_served" not in key_drivers
