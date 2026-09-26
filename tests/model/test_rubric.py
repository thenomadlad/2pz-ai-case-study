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


def test_rubric_handles_missing_rating():
    branches = [
        _features("a", pop=3000, contested_share=0.1, rating=None),
        _features("b", pop=1000, contested_share=0.5, rating=None),
    ]
    decisions = RubricModel().decide(branches, NETWORK)
    assert len(decisions) == 2
