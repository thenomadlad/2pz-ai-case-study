import pytest

from src.model.rubric import PROTECT_AT, SHRINK_AT, RubricModel
from src.models import BranchFeatures, NetworkStats


def _features(branch_id, pop, contested_share, rating, competitors_per_10k=0.0):
    return BranchFeatures(
        branch_id=branch_id, name=branch_id, lat=25.0, lng=55.0,
        female_pop_served=pop, communities_served=1, mean_distance_km=1.0, max_distance_km=1.0,
        contested_pop=0, contested_share=contested_share, nearest_sibling_km=5.0,
        siblings_within_5km=0, avg_price_aed=100.0, price_index=1.0, rating=rating,
        review_count=10, pop_per_1k_rank=0, estimated_fields=[],
        competitors_per_10k=competitors_per_10k,
    )


NETWORK = NetworkStats(
    branch_count=3, total_female_population=6000,
    female_pop_served_median=2000, female_pop_served_p25=1500, female_pop_served_p75=2500,
    contested_share_median=0.2, contested_share_p25=0.1, contested_share_p75=0.3,
    avg_price_aed_median=100, avg_price_aed_p25=90, avg_price_aed_p75=110,
    rating_median=4.3, rating_p25=4.0, rating_p75=4.6,
)


def test_fixed_scales_and_absolute_thresholds():
    strong = _features("strong", pop=150_000, contested_share=0.0, rating=5.0)
    weak = _features("weak", pop=0, contested_share=1.0, rating=4.0, competitors_per_10k=15)
    mid = _features("mid", pop=75_000, contested_share=0.5, rating=4.5, competitors_per_10k=7.5)
    by_id = {d.branch_id: d for d in RubricModel().decide([strong, weak, mid], NETWORK)}

    assert by_id["strong"].composite == pytest.approx(1.0)
    assert by_id["weak"].composite == pytest.approx(0.0)
    assert by_id["mid"].composite == pytest.approx(0.5)
    assert [by_id[i].action for i in ("strong", "mid", "weak")] == ["PROTECT", "HOLD", "SHRINK"]


def test_score_does_not_depend_on_siblings():
    # The whole point of fixed scales: adding a sibling never moves a branch's score.
    a = _features("a", pop=60_000, contested_share=0.3, rating=4.6, competitors_per_10k=4)
    alone = RubricModel().decide([a], NETWORK)[0]
    crowd = RubricModel().decide([a, _features("b", 400_000, 0.0, 5.0)], NETWORK)[0]
    assert alone.composite == crowd.composite and alone.action == crowd.action


def test_healthy_network_can_have_zero_shrinks():
    branches = [_features(str(i), pop=140_000, contested_share=0.1, rating=4.8)
                for i in range(6)]
    assert {d.action for d in RubricModel().decide(branches, NETWORK)} == {"PROTECT"}


def test_missing_rating_scores_neutral_and_lowers_confidence():
    d = RubricModel().decide([_features("a", 150_000, 0.0, None)], NETWORK)[0]
    assert d.scores["quality"] == 0.5
    assert d.confidence == "low"
    assert any("neutral" in c for c in d.caveats)


def test_confidence_low_near_threshold_high_far_from_it():
    # composite = (demand + cannibalisation + competition + quality) / 4
    #           = (0.64 + 1 + 1 + 0) / 4 = 0.66, just over PROTECT_AT
    near = _features("near", pop=96_000, contested_share=0.0, rating=4.0)
    far = _features("far", pop=150_000, contested_share=0.0, rating=5.0)
    by_id = {d.branch_id: d for d in RubricModel().decide([near, far], NETWORK)}
    assert by_id["near"].confidence == "low"
    assert by_id["far"].confidence == "high"
    assert SHRINK_AT < PROTECT_AT


def test_key_drivers_are_the_signals_furthest_from_neutral():
    b = _features("a", pop=75_000, contested_share=0.5, rating=5.0, competitors_per_10k=15)
    d = RubricModel().decide([b], NETWORK)[0]
    assert set(d.key_drivers) == {"quality", "competition"}


def test_empty_branch_list_returns_empty():
    assert RubricModel().decide([], NETWORK) == []
