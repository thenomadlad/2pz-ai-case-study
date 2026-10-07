import json
import logging

from src.config import Settings
from src.config import settings as default_settings
from src.features.build import build_community_features, build_features, load_competitors
from src.model.opportunity import classify_all
from src.model.rubric import RubricModel
from src.models import Branch, BranchFeatures, Community, CommunityAssignment, Decision
from src.scenario.apply import apply_branch_overrides, apply_community_overrides
from src.scenario.baseline import load_baseline_assumptions
from src.scenario.diff import compute_branch_diff, compute_community_diff
from src.scenario.load import load_scenario
from src.scenario.models import Scenario, ScenarioDiff, ScenarioRun

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def run_scenario(scenario: Scenario, settings: Settings | None = None) -> ScenarioRun:
    """Apply a scenario's overrides on top of the fixed baseline raw data, recompute
    features+model, and diff against the baseline report -- entirely in memory. Never writes
    its own output artifacts to disk; callers that need those on disk (the CLI) do that
    themselves with the returned bundle.
    """
    settings = settings or default_settings
    baseline_dir = settings.processed_dir
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

    raw_branches = [Branch(**b) for b in json.loads((raw_dir / "branches.json").read_text())]
    communities = [Community(**c) for c in json.loads((raw_dir / "communities.json").read_text())]
    price_flags = json.loads((raw_dir / "price_flags.json").read_text())
    competitors = load_competitors(raw_dir)

    original_branch_ids = {b.id for b in raw_branches}
    branches = apply_branch_overrides(raw_branches, scenario.overrides.branches)
    communities = apply_community_overrides(communities, scenario.overrides.communities)

    # A scenario-introduced new branch with no avg_price_aed given gets the network median
    # imputed by build_features just like any branch with a missing price -- but its id was
    # never in price_flags (that only comes from the ACQUIRE stage, which never runs for a
    # new scenario entity), so estimated_fields wouldn't flag it. Add those ids explicitly
    # so the imputed price is honestly flagged, not shown as if it were reported.
    new_unpriced_ids = [b.id for b in branches
                         if b.id not in original_branch_ids and b.avg_price_aed is None]
    price_flags = [*price_flags, *new_unpriced_ids]

    contest_ratio = (scenario.assumptions.contest_ratio
                      if scenario.assumptions.contest_ratio is not None
                      else baseline_assumptions.contest_ratio)

    features, network, assignments = build_features(branches, communities, price_flags,
                                                      contest_ratio, competitors)
    community_features = build_community_features(branches, communities, assignments,
                                                  features, competitors)
    decisions = RubricModel().decide(features, network)
    opportunities = classify_all(community_features)

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

    return ScenarioRun(scenario_name=scenario.name, features=features, network=network,
                        assignments=assignments, communities=communities, decisions=decisions,
                        community_features=community_features, opportunities=opportunities,
                        diff=diff)


def main(scenario_path, settings: Settings | None = None) -> None:
    settings = settings or default_settings
    scenario = load_scenario(scenario_path)
    run = run_scenario(scenario, settings)

    current_dir = settings.processed_dir.parent / "current"
    current_dir.mkdir(parents=True, exist_ok=True)

    (current_dir / "branch_features.json").write_text(json.dumps({
        "network": run.network.model_dump(),
        "branches": [f.model_dump() for f in run.features],
    }, indent=2))
    (current_dir / "community_assignment.json").write_text(
        json.dumps([a.model_dump() for a in run.assignments], indent=2))
    (current_dir / "communities.json").write_text(
        json.dumps([c.model_dump() for c in run.communities], indent=2))
    (current_dir / "decisions.json").write_text(
        json.dumps([d.model_dump() for d in run.decisions], indent=2))
    (current_dir / "community_features.json").write_text(
        json.dumps([c.model_dump() for c in run.community_features], indent=2))
    (current_dir / "opportunities.json").write_text(
        json.dumps([o.model_dump() for o in run.opportunities], indent=2))
    (current_dir / "run_meta.json").write_text(
        json.dumps({"model": "rubric", "scenario_name": run.scenario_name}, indent=2))
    (current_dir / "diff.json").write_text(run.diff.model_dump_json(indent=2))

    changed_count = sum(1 for b in run.diff.branches if b.changed_fields or b.old is None)
    reassigned_count = sum(1 for c in run.diff.communities if c.reassigned)
    print(f"scenario: '{run.scenario_name}' -> {len(run.features)} branches, {changed_count} "
          f"changed, {reassigned_count} communities reassigned. Wrote {current_dir}/diff.json")


if __name__ == "__main__":
    import sys
    main(sys.argv[1])
