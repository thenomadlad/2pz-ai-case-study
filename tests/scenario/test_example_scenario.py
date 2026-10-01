import json

from src.config import REPO_ROOT, Settings
from src.scenario.baseline import main as baseline_main
from src.scenario.run import main as scenario_run_main


def test_example_scenario_runs_against_real_seed_data(tmp_path):
    # Real seed_dir/scenarios_dir (the project's actual data), but write raw/processed
    # output to tmp_path so this test doesn't touch the real data/raw or data/processed.
    raw_dir = tmp_path / "raw"
    baseline_dir = tmp_path / "processed" / "baseline"

    # Fix 9: the example scenario's own assumptions now pin model_backend: rubric (Fix 5),
    # but the baseline step reads model_backend from the real, committed
    # data/scenarios/baseline.yaml (still "llm", v0's deliberate default), which only
    # falls back to rubric when no API key is present. Pin anthropic_api_key=None
    # explicitly here (rather than relying on the ambient shell's env being unset) so this
    # test can never make a real network call regardless of what's exported in the
    # environment it happens to run in.
    settings = Settings(_env_file=None, raw_dir=raw_dir, processed_dir=baseline_dir,
                         anthropic_api_key=None)
    baseline_main(settings)

    scenario_path = REPO_ROOT / "data" / "scenarios" / "example-perturbations.yaml"
    scenario_run_main(scenario_path, settings)

    current_dir = baseline_dir.parent / "current"
    features = json.loads((current_dir / "branch_features.json").read_text())
    branch_ids = {b["branch_id"] for b in features["branches"]}
    assert "dubai-marina-new" in branch_ids  # new branch present
    assert len(branch_ids) == 10  # 9 real branches + 1 new

    diff = json.loads((current_dir / "diff.json").read_text())
    by_id = {b["branch_id"]: b for b in diff["branches"]}

    assert by_id["dubai-marina-new"]["old"] is None
    assert by_id["dubai-marina-new"]["action_changed"] is True

    assert by_id["al-safa-2"]["changed_fields"]["lat"] == {"old": 25.1858, "new": 25.2697}
    assert by_id["al-safa-2"]["changed_fields"]["lng"] == {"old": 55.2410, "new": 55.3095}
    # Verified by actually running the corrected scenario (contest_ratio no longer
    # perturbed, model_backend pinned to rubric) against the real seed data: relocating
    # al-safa-2 alone-among-assumptions flips it SHRINK -> PROTECT.
    assert by_id["al-safa-2"]["old"]["action"] == "SHRINK"
    assert by_id["al-safa-2"]["new"]["action"] == "PROTECT"
    assert by_id["al-safa-2"]["action_changed"] is True

    assert by_id["jumeirah-park"]["changed_fields"]["rating"] == {"old": 4.8, "new": 3.9}
    # Verified against the real, corrected run: with the other two overrides (new branch,
    # relocated al-safa-2) also in effect but contest_ratio left at baseline, re-rating
    # jumeirah-park 4.8 -> 3.9 flips it PROTECT -> SHRINK.
    assert by_id["jumeirah-park"]["old"]["action"] == "PROTECT"
    assert by_id["jumeirah-park"]["new"]["action"] == "SHRINK"
    assert by_id["jumeirah-park"]["action_changed"] is True

    # Fix 8: the new branch's imputed price must be flagged as estimated, not shown as a
    # real reported value.
    assert "avg_price_aed" in by_id["dubai-marina-new"]["new"]["estimated_fields"]

    # Honest property of the model (documented in the YAML's comments, Fix 5 item 3): the
    # rubric ranks every branch relative to the whole network, so these three overrides
    # also shift OTHER branches' action even though they were never touched directly.
    other_flips = {b["branch_id"] for b in diff["branches"]
                   if b["action_changed"] and b["branch_id"] not in
                   {"al-safa-2", "jumeirah-park", "dubai-marina-new"}}
    assert other_flips  # verified non-empty by the real run (city-walk, mirdif-35, etc.)

    # Fix 7: both sides of the diff were decided by the same backend here (rubric), since
    # the example scenario now pins model_backend: rubric and the baseline falls back to
    # rubric with no API key set.
    assert diff["baseline_backend"] == "rubric"
    assert diff["current_backend"] == "rubric"

    community_diff = diff["communities"]
    assert len(community_diff) == 50  # all real communities present in the diff
