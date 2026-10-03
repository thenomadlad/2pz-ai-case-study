import dataclasses
import datetime
import json

from src.config import Settings
from src.config import settings as default_settings
from src.models import BranchFeatures, Community, CommunityAssignment, Decision, NetworkStats


@dataclasses.dataclass
class BaselineData:
    features: list[BranchFeatures]
    decisions: list[Decision]
    assignments: list[CommunityAssignment]
    communities: list[Community]
    network: NetworkStats
    model_backend: str
    data_sources: dict[str, str]
    pipeline_run_at: datetime.datetime

    def decision_for(self, branch_id: str) -> Decision | None:
        return next((d for d in self.decisions if d.branch_id == branch_id), None)

    def communities_by_id(self) -> dict[str, Community]:
        return {c.id: c for c in self.communities}


def load_baseline(settings: Settings | None = None) -> BaselineData:
    settings = settings or default_settings
    processed_dir = settings.processed_dir

    payload = json.loads((processed_dir / "branch_features.json").read_text())
    network = NetworkStats(**payload["network"])
    features = [BranchFeatures(**b) for b in payload["branches"]]
    decisions = [Decision(**d) for d in
                 json.loads((processed_dir / "decisions.json").read_text())]
    assignments = [CommunityAssignment(**a) for a in
                   json.loads((processed_dir / "community_assignment.json").read_text())]
    communities = [Community(**c) for c in
                   json.loads((processed_dir / "communities.json").read_text())]

    run_meta_path = processed_dir / "run_meta.json"
    if run_meta_path.exists():
        model_backend = json.loads(run_meta_path.read_text())["model_backend"]
    else:
        model_backend = settings.model_backend

    data_sources = {
        "branches": "seed" if not settings.enable_scrape else "seed (scrape unimplemented)",
        "communities": "seed" if not settings.dubai_pulse_enabled
                        else "seed (pulse unimplemented)",
    }
    mtime = (processed_dir / "branch_features.json").stat().st_mtime

    return BaselineData(
        features=features, decisions=decisions, assignments=assignments,
        communities=communities, network=network, model_backend=model_backend,
        data_sources=data_sources,
        pipeline_run_at=datetime.datetime.fromtimestamp(mtime, tz=datetime.UTC),
    )
