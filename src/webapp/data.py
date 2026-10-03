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


def _ensure_baseline(settings: Settings) -> None:
    # A fresh clone (including a fresh Streamlit Community Cloud deploy) has no
    # data/processed/baseline/ -- it's gitignored, generated output. Generate it from the
    # committed seed data the first time it's missing, so the app is self-contained rather
    # than depending on someone having run `just all` first. Idempotent: once the file
    # exists, every later load_baseline() call skips straight past this. Falls back to the
    # rubric backend automatically when no ANTHROPIC_API_KEY is configured (existing
    # resolve_backend behavior), so a fresh public deploy never silently spends API budget.
    # run_meta.json is the LAST file model/run.py writes -- checking for it (not
    # branch_features.json, written earlier by the features stage) means a baseline that
    # failed partway through generation (e.g. a transient LLM API error) is recognized as
    # incomplete and retried on the next load, rather than permanently wedged with a
    # present branch_features.json but a missing decisions.json.
    if (settings.processed_dir / "run_meta.json").exists():
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
