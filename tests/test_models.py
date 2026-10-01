import pytest
from pydantic import ValidationError

from src.models import (
    Branch, Community, CommunityAssignment, BranchFeatures, NetworkStats, Decision,
)


def test_branch_minimal():
    b = Branch(id="al-barsha", name="Al Barsha", lat=25.11, lng=55.20, area="Al Barsha",
               rating=None, review_count=None, avg_price_aed=None, source="seed")
    assert b.id == "al-barsha"
    assert b.rating is None


def test_branch_accepts_scenario_source():
    b = Branch(id="new-branch", name="New Branch", lat=25.0, lng=55.0, area="Somewhere",
               rating=None, review_count=None, avg_price_aed=None, source="scenario")
    assert b.source == "scenario"


def test_community_estimated_flag_required():
    c = Community(id="c1", name_en="Deira", lat=25.27, lng=55.31,
                   population_total=1000, population_female=None, is_estimated=True)
    assert c.is_estimated is True
    assert c.population_female is None


def test_community_assignment_contested():
    a = CommunityAssignment(community_id="c1", nearest_branch_id="b1", nearest_km=1.2,
                             second_branch_id="b2", second_km=1.3, contested=True, female_pop=500)
    assert a.contested is True


def test_branch_features_estimated_fields_default_empty():
    f = BranchFeatures(branch_id="b1", name="Al Barsha", lat=25.11, lng=55.20,
                        female_pop_served=1000, communities_served=3, mean_distance_km=1.5,
                        max_distance_km=3.0, contested_pop=100, contested_share=0.1,
                        nearest_sibling_km=4.0, siblings_within_5km=1, avg_price_aed=150.0,
                        price_index=1.0, rating=4.5, review_count=200, pop_per_1k_rank=1,
                        estimated_fields=[])
    assert f.estimated_fields == []


def test_network_stats():
    n = NetworkStats(branch_count=10, total_female_population=50000,
                      female_pop_served_median=5000, female_pop_served_p25=3000,
                      female_pop_served_p75=7000, contested_share_median=0.2,
                      contested_share_p25=0.1, contested_share_p75=0.3,
                      avg_price_aed_median=150, avg_price_aed_p25=120, avg_price_aed_p75=180,
                      rating_median=4.3, rating_p25=4.0, rating_p75=4.6)
    assert n.branch_count == 10


def test_decision_rejects_bad_action():
    with pytest.raises(ValidationError):
        Decision(branch_id="b1", action="EXPAND", confidence="low",
                  rationale="x", key_drivers=[], caveats=[])


def test_decision_valid_action():
    d = Decision(branch_id="b1", action="PROTECT", confidence="high",
                 rationale="Serves the most women with low contest.",
                 key_drivers=["female_pop_served", "contested_share"], caveats=["No revenue data."])
    assert d.action == "PROTECT"
