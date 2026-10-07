import json

from src.config import REPO_ROOT, Settings
from src.scenario.baseline import main as baseline_main
from src.scenario.run import main as scenario_run_main


def test_example_scenario_runs_against_real_seed_data(tmp_path):
    # Real seed_dir/scenarios_dir (the project's actual data), but write raw/processed
    # output to tmp_path so this test doesn't touch the real data/raw or data/processed.
    raw_dir = tmp_path / "raw"
    baseline_dir = tmp_path / "processed" / "baseline"

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
    # Verified against the real run: moving the network's one SHRINK branch into Deira, an
    # uncovered area, gives it a large uncontested catchment -> PROTECT.
    assert by_id["al-safa-2"]["old"]["action"] == "SHRINK"
    assert by_id["al-safa-2"]["new"]["action"] == "PROTECT"
    assert by_id["al-safa-2"]["action_changed"] is True

    assert by_id["jumeirah-park"]["changed_fields"]["rating"] == {"old": 4.8, "new": 3.9}
    # Fixed scales: a 3.9 rating zeroes the quality score, but demand, cannibalisation and
    # competition are all strong, so the branch stays PROTECT.
    assert by_id["jumeirah-park"]["new"]["action"] == "PROTECT"
    assert by_id["jumeirah-park"]["action_changed"] is False

    # The new branch's imputed price must be flagged as estimated.
    assert "avg_price_aed" in by_id["dubai-marina-new"]["new"]["estimated_fields"]

    # Untouched branches can still flip: the new and moved branches take communities (and
    # their competitors) out of neighbouring catchments.
    other_flips = {b["branch_id"] for b in diff["branches"]
                   if b["action_changed"] and b["branch_id"] not in
                   {"al-safa-2", "jumeirah-park", "dubai-marina-new"}}
    assert other_flips  # mirdif-35 and palm-jumeirah in the real run

    community_diff = diff["communities"]
    assert len(community_diff) == 50  # all real communities present in the diff

    # Covering Deira turns its GROW areas into WATCH.
    baseline_opp = {o["community_id"]: o["action"] for o in
                    json.loads((baseline_dir / "opportunities.json").read_text())}
    current_opp = {o["community_id"]: o["action"] for o in
                   json.loads((current_dir / "opportunities.json").read_text())}
    assert baseline_opp["naif"] == "GROW" and current_opp["naif"] == "WATCH"
