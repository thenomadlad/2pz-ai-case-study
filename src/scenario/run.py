import json
import logging

from src.config import Settings
from src.config import settings as default_settings
from src.features.build import build_features
from src.model.run import resolve_backend
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
    themselves with the returned bundle. (If the llm backend is selected, LLMModel's own
    response cache is a separate, pre-existing side effect of src/model/llm.py -- see the
    comment below, not a disk write performed by run_scenario() itself.)
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
    model_backend = (scenario.assumptions.model_backend
                      if scenario.assumptions.model_backend is not None
                      else baseline_assumptions.model_backend)

    # Redirect processed_dir (not an on-disk write by itself) so that IF the llm backend is
    # used, its own response cache lands under data/processed/current/.llm_cache rather than
    # inside baseline/, which must never be touched by a scenario run. This is a pre-existing
    # side effect of LLMModel itself (src/model/llm.py, untouched by this refactor) -- it is
    # NOT one of run_scenario()'s own output artifacts (those are only ever written by main(),
    # never here). The widget-based Streamlit editor defaults to the rubric backend
    # specifically so the live perturbation loop never depends on this cache existing.
    current_dir = baseline_dir.parent / "current"
    current_settings = settings.model_copy(update={
        "processed_dir": current_dir,
        "contest_ratio": contest_ratio,
        "model_backend": model_backend,
    })

    features, network, assignments = build_features(branches, communities, price_flags,
                                                      contest_ratio)
    model = resolve_backend(current_settings)
    decisions = model.decide(features, network)

    baseline_payload = json.loads((baseline_dir / "branch_features.json").read_text())
    baseline_features = [BranchFeatures(**b) for b in baseline_payload["branches"]]
    baseline_decisions = [Decision(**d) for d in
                           json.loads((baseline_dir / "decisions.json").read_text())]
    baseline_assignments = [CommunityAssignment(**a) for a in
                             json.loads((baseline_dir / "community_assignment.json").read_text())]

    # Records which backend produced each side of the diff, the same way the old /api/network
    # read it, so a flip can be attributed to "inputs changed" vs. "decision method changed".
    baseline_run_meta_path = baseline_dir / "run_meta.json"
    if baseline_run_meta_path.exists():
        baseline_backend = json.loads(baseline_run_meta_path.read_text())["model_backend"]
    else:
        baseline_backend = settings.model_backend

    branch_diff = compute_branch_diff(baseline_features, baseline_decisions, features, decisions)
    community_diff = compute_community_diff(baseline_assignments, assignments)
    diff = ScenarioDiff(scenario_name=scenario.name, branches=branch_diff,
                         communities=community_diff,
                         baseline_backend=baseline_backend, current_backend=model.name)

    return ScenarioRun(scenario_name=scenario.name, features=features, network=network,
                        assignments=assignments, communities=communities, decisions=decisions,
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
    (current_dir / "run_meta.json").write_text(
        json.dumps({"model_backend": run.diff.current_backend,
                     "scenario_name": run.scenario_name}, indent=2))
    (current_dir / "diff.json").write_text(run.diff.model_dump_json(indent=2))

    changed_count = sum(1 for b in run.diff.branches if b.changed_fields or b.old is None)
    reassigned_count = sum(1 for c in run.diff.communities if c.reassigned)
    print(f"scenario: '{run.scenario_name}' -> {len(run.features)} branches, {changed_count} "
          f"changed, {reassigned_count} communities reassigned. Wrote {current_dir}/diff.json")


if __name__ == "__main__":
    import sys
    main(sys.argv[1])
