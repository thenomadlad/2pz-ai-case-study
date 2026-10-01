import csv
import json

import yaml

from src.config import Settings
from src.scenario.run import main


def _write_seed_and_baseline(tmp_path):
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    with open(seed_dir / "branches.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "id", "name", "lat", "lng", "area", "rating", "review_count", "avg_price_aed"])
        w.writeheader()
        w.writerow({"id": "a", "name": "A", "lat": "25.10", "lng": "55.20", "area": "Area A",
                    "rating": "4.5", "review_count": "100", "avg_price_aed": "99"})
        w.writerow({"id": "b", "name": "B", "lat": "25.50", "lng": "55.50", "area": "Area B",
                    "rating": "4.0", "review_count": "50", "avg_price_aed": "99"})
    with open(seed_dir / "communities.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "id", "name_en", "lat", "lng", "population_total", "population_female"])
        w.writeheader()
        w.writerow({"id": "c1", "name_en": "C1", "lat": "25.11", "lng": "55.21",
                    "population_total": "1000", "population_female": "490"})

    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "baseline.yaml").write_text(yaml.dump({
        "assumptions": {"contest_ratio": 1.25, "model_backend": "rubric"},
    }))

    raw_dir = tmp_path / "raw"
    baseline_dir = tmp_path / "processed" / "baseline"

    from src.scenario.baseline import main as baseline_main
    baseline_settings = Settings(_env_file=None, seed_dir=seed_dir, raw_dir=raw_dir,
                                  processed_dir=baseline_dir)
    baseline_main(baseline_settings)
    return seed_dir, raw_dir, baseline_dir, scenarios_dir


def test_scenario_run_writes_current_and_diff(tmp_path):
    seed_dir, raw_dir, baseline_dir, scenarios_dir = _write_seed_and_baseline(tmp_path)

    scenario_path = scenarios_dir / "test-scenario.yaml"
    scenario_path.write_text(yaml.dump({
        "name": "test-scenario",
        "assumptions": {"model_backend": "rubric"},
        "overrides": {
            "branches": {
                "a": {"rating": 3.0},
                "new-branch": {"name": "New Branch", "lat": 25.3, "lng": 55.3, "area": "New Area"},
            },
        },
    }))

    settings = Settings(_env_file=None, seed_dir=seed_dir, raw_dir=raw_dir,
                         processed_dir=baseline_dir)
    main(scenario_path, settings)

    current_dir = baseline_dir.parent / "current"
    features = json.loads((current_dir / "branch_features.json").read_text())
    assert len(features["branches"]) == 3  # a, b, new-branch

    diff = json.loads((current_dir / "diff.json").read_text())
    assert diff["scenario_name"] == "test-scenario"
    by_id = {b["branch_id"]: b for b in diff["branches"]}
    assert by_id["a"]["changed_fields"]["rating"] == {"old": 4.5, "new": 3.0}
    assert by_id["new-branch"]["old"] is None
    assert by_id["new-branch"]["action_changed"] is True


def test_scenario_run_raises_when_baseline_missing(tmp_path):
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "baseline.yaml").write_text(yaml.dump({"assumptions": {}}))
    scenario_path = scenarios_dir / "s.yaml"
    scenario_path.write_text(yaml.dump({"name": "s"}))

    settings = Settings(_env_file=None, seed_dir=seed_dir, raw_dir=tmp_path / "raw",
                         processed_dir=tmp_path / "processed" / "baseline")

    import pytest
    with pytest.raises(FileNotFoundError):
        main(scenario_path, settings)
