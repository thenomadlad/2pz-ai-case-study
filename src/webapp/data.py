import dataclasses
import datetime
import json

from src.config import Settings
from src.config import settings as default_settings
from src.features.assign import haversine_km
from src.features.build import load_competitors
from src.models import (
    BranchFeatures,
    Community,
    CommunityAssignment,
    CommunityFeatures,
    Competitor,
    Decision,
    NetworkStats,
    OpportunityDecision,
)


@dataclasses.dataclass
class BaselineData:
    features: list[BranchFeatures]
    decisions: list[Decision]
    assignments: list[CommunityAssignment]
    communities: list[Community]
    network: NetworkStats
    community_features: list[CommunityFeatures]
    opportunities: list[OpportunityDecision]
    competitors: list[Competitor]
    data_sources: dict[str, str]
    pipeline_run_at: datetime.datetime

    def decision_for(self, branch_id: str) -> Decision | None:
        return next((d for d in self.decisions if d.branch_id == branch_id), None)

    def opportunity_for(self, community_id: str) -> OpportunityDecision | None:
        return next((o for o in self.opportunities if o.community_id == community_id), None)

    def area_of(self, branch_id: str) -> str:
        """The community hosting a branch: its nearest community centroid (the same rule as
        CommunityFeatures.hosts_branch)."""
        f = next(f for f in self.features if f.branch_id == branch_id)
        return min(self.community_features,
                   key=lambda c: haversine_km(f.lat, f.lng, c.lat, c.lng)).community_id

    def branches_in(self, community_id: str) -> list[BranchFeatures]:
        return [f for f in self.features if self.area_of(f.branch_id) == community_id]

    def with_scenario(self, run) -> "BaselineData":
        """The same view, with a ScenarioRun's recomputed numbers and decisions."""
        return dataclasses.replace(
            self, features=run.features, decisions=run.decisions, assignments=run.assignments,
            communities=run.communities, network=run.network,
            community_features=run.community_features, opportunities=run.opportunities)

    def communities_by_id(self) -> dict[str, Community]:
        return {c.id: c for c in self.communities}


def _ensure_baseline(settings: Settings) -> None:
    # A fresh clone (including a fresh Streamlit Community Cloud deploy) has no
    # data/processed/baseline/ -- it's gitignored, generated output. Generate it from the
    # committed seed data the first time it's missing, so the app is self-contained rather
    # than depending on someone having run `just all` first. Idempotent: once the file
    # exists, every later load_baseline() call skips straight past this.
    # run_meta.json is the LAST file model/run.py writes -- checking for it (not
    # branch_features.json, written earlier by the features stage) means a baseline that
    # failed partway through generation is recognized as incomplete and retried on the
    # next load, rather than permanently wedged with a missing decisions.json. A baseline
    # from an older pipeline version is regenerated the same way.
    from src.model.run import PIPELINE_VERSION

    run_meta = settings.processed_dir / "run_meta.json"
    if (run_meta.exists()
            and json.loads(run_meta.read_text()).get("pipeline_version") == PIPELINE_VERSION):
        return
    from src.scenario.baseline import main as generate_baseline
    generate_baseline(settings)


def load_baseline(settings: Settings | None = None) -> BaselineData:
    settings = settings or default_settings
    processed_dir = settings.processed_dir
    _ensure_baseline(settings)

    payload = json.loads((processed_dir / "branch_features.json").read_text())
    network = NetworkStats(**payload["network"])
    features = [BranchFeatures(**b) for b in payload["branches"]]
    decisions = [Decision(**d) for d in
                 json.loads((processed_dir / "decisions.json").read_text())]
    assignments = [CommunityAssignment(**a) for a in
                   json.loads((processed_dir / "community_assignment.json").read_text())]
    communities = [Community(**c) for c in
                   json.loads((processed_dir / "communities.json").read_text())]

    community_features = [CommunityFeatures(**c) for c in
                          json.loads((processed_dir / "community_features.json").read_text())]
    opportunities = [OpportunityDecision(**o) for o in
                     json.loads((processed_dir / "opportunities.json").read_text())]

    data_sources = {
        "branches": "seed (2GIS)",
        "communities": "seed (Dubai Statistics Center)",
        "competitors": "OpenStreetMap seed",
    }
    mtime = (processed_dir / "branch_features.json").stat().st_mtime

    return BaselineData(
        features=features, decisions=decisions, assignments=assignments,
        communities=communities, network=network,
        community_features=community_features, opportunities=opportunities,
        competitors=load_competitors(settings.raw_dir),
        data_sources=data_sources,
        pipeline_run_at=datetime.datetime.fromtimestamp(mtime, tz=datetime.UTC),
    )
