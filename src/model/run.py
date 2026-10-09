import json

from src.config import Settings
from src.config import settings as default_settings
from src.model.opportunity import classify_all
from src.model.rubric import RubricModel
from src.models import BranchFeatures, CommunityFeatures, NetworkStats

# Bump when processed outputs change shape; the app regenerates an older baseline.
PIPELINE_VERSION = 3


def main(settings: Settings | None = None) -> None:
    settings = settings or default_settings
    payload = json.loads((settings.processed_dir / "branch_features.json").read_text())
    network = NetworkStats(**payload["network"])
    branches = [BranchFeatures(**b) for b in payload["branches"]]
    communities = [CommunityFeatures(**c) for c in json.loads(
        (settings.processed_dir / "community_features.json").read_text())]

    decisions = RubricModel().decide(branches, network)
    opportunities = classify_all(communities)

    (settings.processed_dir / "decisions.json").write_text(
        json.dumps([d.model_dump() for d in decisions], indent=2))
    (settings.processed_dir / "opportunities.json").write_text(
        json.dumps([o.model_dump() for o in opportunities], indent=2))
    # Written last: data.py treats its presence as "baseline complete".
    (settings.processed_dir / "run_meta.json").write_text(
        json.dumps({"model": "rubric", "pipeline_version": PIPELINE_VERSION}, indent=2))

    print(f"model: wrote {len(decisions)} branch decisions, {len(opportunities)} opportunities")


if __name__ == "__main__":
    main()
