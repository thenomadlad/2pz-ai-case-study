from typing import Any

from pydantic import BaseModel, ConfigDict

from src.models import (
    BranchFeatures,
    Community,
    CommunityAssignment,
    CommunityFeatures,
    Decision,
    NetworkStats,
    OpportunityDecision,
)


class BaselineAssumptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contest_ratio: float = 1.25
    global_female_share: float = 0.49
    fallback_price_aed: float = 99.0


class ScenarioAssumptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contest_ratio: float | None = None


class ScenarioOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branches: dict[str, dict[str, Any]] = {}
    communities: dict[str, dict[str, Any]] = {}


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    assumptions: ScenarioAssumptions = ScenarioAssumptions()
    overrides: ScenarioOverrides = ScenarioOverrides()


class BranchDiffEntry(BaseModel):
    branch_id: str
    old: dict[str, Any] | None
    new: dict[str, Any] | None
    changed_fields: dict[str, dict[str, Any]]
    action_changed: bool


class CommunityDiffEntry(BaseModel):
    community_id: str
    reassigned: bool
    old_branch_id: str | None
    new_branch_id: str | None


class ScenarioDiff(BaseModel):
    scenario_name: str
    branches: list[BranchDiffEntry]
    communities: list[CommunityDiffEntry]


class ScenarioRun(BaseModel):
    scenario_name: str
    features: list[BranchFeatures]
    network: NetworkStats
    assignments: list[CommunityAssignment]
    communities: list[Community]
    decisions: list[Decision]
    community_features: list[CommunityFeatures]
    opportunities: list[OpportunityDecision]
    diff: ScenarioDiff
