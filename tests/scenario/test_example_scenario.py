import json

from src.config import REPO_ROOT, Settings
from src.scenario.baseline import main as baseline_main
from src.scenario.run import main as scenario_run_main


def test_example_scenario_runs_against_real_seed_data(tmp_path):
    # Real seed_dir/scenarios_dir (the project's actual data), but write raw/processed
    # output to tmp_path so this test doesn't touch the real data/raw or data/processed.
    raw_dir = tmp_path / "raw"
    baseline_dir = tmp_path / "processed" / "baseline"

    settings = Settings(_env_file=None, raw_dir=raw_dir, processed_dir=baseline_dir)
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

    assert by_id["jumeirah-park"]["changed_fields"]["rating"] == {"old": 4.8, "new": 3.9}
    # action_changed may be True or False depending on where 3.9 lands in the rubric's
    # ranking -- both are valid outcomes, the point is changed_fields shows the real delta
    # regardless of whether it flipped the tier.

    community_diff = diff["communities"]
    assert len(community_diff) == 50  # all real communities present in the diff
