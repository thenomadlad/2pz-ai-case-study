# tests/scenario/test_diff.py
from src.models import BranchFeatures, CommunityAssignment, Decision
from src.scenario.diff import compute_branch_diff, compute_community_diff


def _features(branch_id, rating=4.5, female_pop_served=1000):
    return BranchFeatures(
        branch_id=branch_id, name=branch_id, lat=25.0, lng=55.0,
        female_pop_served=female_pop_served, communities_served=1, mean_distance_km=1.0,
        max_distance_km=1.0, contested_pop=0, contested_share=0.0, nearest_sibling_km=5.0,
        siblings_within_5km=0, avg_price_aed=99.0, price_index=1.0, rating=rating,
        review_count=10, pop_per_1k_rank=1, estimated_fields=[],
    )


def _decision(branch_id, action="PROTECT"):
    return Decision(branch_id=branch_id, action=action, confidence="medium",
                     rationale="x", key_drivers=[], caveats=[])


def test_branch_diff_detects_changed_field():
    baseline_features = [_features("a", rating=4.5)]
    current_features = [_features("a", rating=3.9)]
    baseline_decisions = [_decision("a", "PROTECT")]
    current_decisions = [_decision("a", "PROTECT")]

    entries = compute_branch_diff(baseline_features, baseline_decisions,
                                   current_features, current_decisions)

    assert len(entries) == 1
    assert entries[0].branch_id == "a"
    assert entries[0].changed_fields["rating"] == {"old": 4.5, "new": 3.9}
    assert entries[0].action_changed is False
    assert entries[0].old is not None
    assert entries[0].new is not None


def test_branch_diff_detects_action_change():
    baseline_features = [_features("a")]
    current_features = [_features("a")]
    entries = compute_branch_diff(baseline_features, [_decision("a", "PROTECT")],
                                   current_features, [_decision("a", "SHRINK")])

    assert entries[0].action_changed is True
    assert entries[0].old["action"] == "PROTECT"
    assert entries[0].new["action"] == "SHRINK"


def test_branch_diff_new_branch_has_no_old():
    entries = compute_branch_diff([], [], [_features("new-one")], [_decision("new-one")])

    assert len(entries) == 1
    assert entries[0].old is None
    assert entries[0].new is not None
    assert entries[0].action_changed is True  # None -> an action is a change


def test_branch_diff_no_changes_when_identical():
    features = [_features("a")]
    decisions = [_decision("a")]
    entries = compute_branch_diff(features, decisions, features, decisions)

    assert entries[0].changed_fields == {}
    assert entries[0].action_changed is False


def test_community_diff_detects_reassignment():
    baseline = [CommunityAssignment(community_id="c1", nearest_branch_id="a", nearest_km=1.0,
                                     second_branch_id=None, second_km=None, contested=False,
                                     female_pop=500)]
    current = [CommunityAssignment(community_id="c1", nearest_branch_id="b", nearest_km=2.0,
                                    second_branch_id=None, second_km=None, contested=False,
                                    female_pop=500)]

    entries = compute_community_diff(baseline, current)

    assert len(entries) == 1
    assert entries[0].reassigned is True
    assert entries[0].old_branch_id == "a"
    assert entries[0].new_branch_id == "b"


def test_community_diff_no_reassignment():
    assignment = CommunityAssignment(community_id="c1", nearest_branch_id="a", nearest_km=1.0,
                                      second_branch_id=None, second_km=None, contested=False,
                                      female_pop=500)
    entries = compute_community_diff([assignment], [assignment])

    assert entries[0].reassigned is False
