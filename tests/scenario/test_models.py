import pytest
from pydantic import ValidationError

from src.scenario.models import (
    BaselineAssumptions,
    BranchDiffEntry,
    CommunityDiffEntry,
    Scenario,
    ScenarioAssumptions,
    ScenarioDiff,
    ScenarioOverrides,
)


def test_baseline_assumptions_defaults():
    a = BaselineAssumptions()
    assert a.contest_ratio == 1.25
    assert a.global_female_share == 0.49
    assert a.fallback_price_aed == 99.0
    assert a.model_backend == "llm"


def test_baseline_assumptions_rejects_unknown_field():
    with pytest.raises(ValidationError):
        BaselineAssumptions(continue_ratio=1.1)  # typo'd field name


def test_scenario_assumptions_default_to_none():
    a = ScenarioAssumptions()
    assert a.contest_ratio is None
    assert a.model_backend is None


def test_scenario_minimal():
    s = Scenario(name="test-scenario")
    assert s.name == "test-scenario"
    assert s.assumptions.contest_ratio is None
    assert s.overrides.branches == {}
    assert s.overrides.communities == {}


def test_scenario_with_overrides():
    s = Scenario(name="test", overrides=ScenarioOverrides(
        branches={"al-safa-2": {"lat": 25.27, "lng": 55.31}},
        communities={"deira": {"population_female": 9000}},
    ))
    assert s.overrides.branches["al-safa-2"]["lat"] == 25.27
    assert s.overrides.communities["deira"]["population_female"] == 9000


def test_branch_diff_entry_new_branch_has_no_old():
    entry = BranchDiffEntry(branch_id="new-one", old=None, new={"action": "PROTECT"},
                             changed_fields={}, action_changed=True)
    assert entry.old is None
    assert entry.new["action"] == "PROTECT"


def test_community_diff_entry_reassigned():
    entry = CommunityDiffEntry(community_id="c1", reassigned=True,
                                old_branch_id="a", new_branch_id="b")
    assert entry.reassigned is True


def test_scenario_diff_shape():
    diff = ScenarioDiff(scenario_name="x", branches=[], communities=[],
                         baseline_backend="rubric", current_backend="rubric")
    assert diff.scenario_name == "x"
    assert diff.branches == []


def test_scenario_diff_carries_backend_names():
    diff = ScenarioDiff(scenario_name="x", branches=[], communities=[],
                         baseline_backend="llm", current_backend="rubric")
    assert diff.baseline_backend == "llm"
    assert diff.current_backend == "rubric"
