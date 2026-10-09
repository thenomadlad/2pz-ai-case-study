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
    # Drive time a customer will travel to a salon; sources in data/seed/v3/SOURCES.md.
    travel_time_minutes: dict[str, int] = {"low": 10, "medium": 15, "high": 20}
    # Departure time for traffic-aware isochrones (Mapbox driving-traffic), local time.
    isochrone_depart_at: str = "2026-10-13T12:00"
    # Competitors: top-k premium substitutes per lounge. See SOURCES.md, "Competitors".
    bedashing_price_level: str = "expensive"
    comparable_price_levels: list[str] = ["expensive", "very_expensive"]
    premium_min_rating: float = 4.3
    competitor_coverage: dict[str, float] = {"low": 0.5, "medium": 0.6, "high": 0.7}
    search_recall: float = 0.66
    # Female share of adults in worker housing (OSM industrial land use); calibrated on
    # Dubai Statistics Center labour-camp communities. See SOURCES.md, "Market size".
    worker_housing_female_share: dict[str, float] = {"low": 0.01, "medium": 0.055, "high": 0.15}


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
