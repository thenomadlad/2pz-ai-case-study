import json
import logging
import sys

from src.config import Settings, settings as default_settings
from src.features.build import build_features
from src.model.run import resolve_backend
from src.models import Branch, BranchFeatures, Community, CommunityAssignment, Decision
from src.scenario.apply import apply_branch_overrides, apply_community_overrides
from src.scenario.baseline import load_baseline_assumptions
from src.scenario.diff import compute_branch_diff, compute_community_diff
from src.scenario.load import load_scenario
from src.scenario.models import ScenarioDiff

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main(scenario_path, settings: Settings | None = None) -> None:
    settings = settings or default_settings
    baseline_dir = settings.processed_dir
    current_dir = baseline_dir.parent / "current"
    raw_dir = settings.raw_dir
    scenarios_dir = settings.seed_dir.parent / "scenarios"

    if not (raw_dir / "branches.json").exists():
        raise FileNotFoundError(
            f"{raw_dir}/branches.json not found -- run `just all` to produce the baseline "
            "raw data before running a scenario."
        )
    if not (baseline_dir / "branch_features.json").exists():
        raise FileNotFoundError(
            f"{baseline_dir}/branch_features.json not found -- run `just all` to produce "
            "the baseline report before running a scenario."
        )

    baseline_assumptions = load_baseline_assumptions(scenarios_dir / "baseline.yaml")
    scenario = load_scenario(scenario_path)

    branches = [Branch(**b) for b in json.loads((raw_dir / "branches.json").read_text())]
    communities = [Community(**c) for c in json.loads((raw_dir / "communities.json").read_text())]
    price_flags = json.loads((raw_dir / "price_flags.json").read_text())

    branches = apply_branch_overrides(branches, scenario.overrides.branches)
    communities = apply_community_overrides(communities, scenario.overrides.communities)

    contest_ratio = (scenario.assumptions.contest_ratio
                      if scenario.assumptions.contest_ratio is not None
                      else baseline_assumptions.contest_ratio)
    model_backend = (scenario.assumptions.model_backend
                      if scenario.assumptions.model_backend is not None
                      else baseline_assumptions.model_backend)

    current_dir.mkdir(parents=True, exist_ok=True)
    current_settings = settings.model_copy(update={
        "processed_dir": current_dir,
        "contest_ratio": contest_ratio,
        "model_backend": model_backend,
    })

    features, network, assignments = build_features(branches, communities, price_flags,
                                                      contest_ratio)
    model = resolve_backend(current_settings)
    decisions = model.decide(features, network)

    (current_dir / "branch_features.json").write_text(json.dumps({
        "network": network.model_dump(),
        "branches": [f.model_dump() for f in features],
    }, indent=2))
    (current_dir / "community_assignment.json").write_text(
        json.dumps([a.model_dump() for a in assignments], indent=2))
    (current_dir / "communities.json").write_text(
        json.dumps([c.model_dump() for c in communities], indent=2))
    (current_dir / "decisions.json").write_text(
        json.dumps([d.model_dump() for d in decisions], indent=2))
    (current_dir / "run_meta.json").write_text(
        json.dumps({"model_backend": model.name, "scenario_name": scenario.name}, indent=2))

    baseline_payload = json.loads((baseline_dir / "branch_features.json").read_text())
    baseline_features = [BranchFeatures(**b) for b in baseline_payload["branches"]]
    baseline_decisions = [Decision(**d) for d in
                           json.loads((baseline_dir / "decisions.json").read_text())]
    baseline_assignments = [CommunityAssignment(**a) for a in
                             json.loads((baseline_dir / "community_assignment.json").read_text())]

    branch_diff = compute_branch_diff(baseline_features, baseline_decisions, features, decisions)
    community_diff = compute_community_diff(baseline_assignments, assignments)
    diff = ScenarioDiff(scenario_name=scenario.name, branches=branch_diff,
                         communities=community_diff)
    (current_dir / "diff.json").write_text(diff.model_dump_json(indent=2))

    changed_count = sum(1 for b in branch_diff if b.changed_fields or b.old is None)
    reassigned_count = sum(1 for c in community_diff if c.reassigned)
    print(f"scenario: '{scenario.name}' -> {len(features)} branches, {changed_count} changed, "
          f"{reassigned_count} communities reassigned. Wrote {current_dir}/diff.json")


if __name__ == "__main__":
    main(sys.argv[1])
