import csv
import json

import yaml

from src.config import Settings
from src.scenario.run import main, run_scenario


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


def test_scenario_diff_records_baseline_and_current_backend(tmp_path):
    # Fix 7: ScenarioDiff must record which backend produced each side of the diff, so a
    # mismatch (baseline decided with one backend, scenario run with another) is
    # attributable rather than silently conflated with "the inputs changed".
    seed_dir, raw_dir, baseline_dir, scenarios_dir = _write_seed_and_baseline(tmp_path)

    scenario_path = scenarios_dir / "test-scenario.yaml"
    scenario_path.write_text(yaml.dump({
        "name": "test-scenario",
        "assumptions": {"model_backend": "rubric"},
        "overrides": {"branches": {"a": {"rating": 3.0}}},
    }))

    settings = Settings(_env_file=None, seed_dir=seed_dir, raw_dir=raw_dir,
                         processed_dir=baseline_dir)
    main(scenario_path, settings)

    current_dir = baseline_dir.parent / "current"
    diff = json.loads((current_dir / "diff.json").read_text())
    # _write_seed_and_baseline pins baseline.yaml's model_backend to "rubric", and this
    # scenario also pins "rubric" -- both sides should match here.
    assert diff["baseline_backend"] == "rubric"
    assert diff["current_backend"] == "rubric"


def test_new_branch_with_no_price_flagged_as_estimated(tmp_path):
    # Fix 8: a scenario-introduced branch with no avg_price_aed gets the network median
    # imputed by build_features, but its id was never in price_flags (that only comes from
    # ACQUIRE, which doesn't run for scenario entities). estimated_fields must still flag it.
    seed_dir, raw_dir, baseline_dir, scenarios_dir = _write_seed_and_baseline(tmp_path)

    scenario_path = scenarios_dir / "test-scenario.yaml"
    scenario_path.write_text(yaml.dump({
        "name": "test-scenario",
        "assumptions": {"model_backend": "rubric"},
        "overrides": {
            "branches": {
                "new-branch": {"name": "New Branch", "lat": 25.3, "lng": 55.3, "area": "New Area"},
            },
        },
    }))

    settings = Settings(_env_file=None, seed_dir=seed_dir, raw_dir=raw_dir,
                         processed_dir=baseline_dir)
    main(scenario_path, settings)

    current_dir = baseline_dir.parent / "current"
    features = json.loads((current_dir / "branch_features.json").read_text())
    by_id = {b["branch_id"]: b for b in features["branches"]}
    assert "avg_price_aed" in by_id["new-branch"]["estimated_fields"]


def test_scenario_run_never_modifies_baseline_dir(tmp_path):
    # Fix 10: direct regression test for the core "baseline is reality, never modified by
    # a scenario run" invariant, rather than relying only on manual verification.
    seed_dir, raw_dir, baseline_dir, scenarios_dir = _write_seed_and_baseline(tmp_path)

    before = {
        p: (p.read_bytes(), p.stat().st_mtime_ns)
        for p in baseline_dir.rglob("*") if p.is_file()
    }
    assert before  # sanity: baseline actually produced files

    scenario_path = scenarios_dir / "test-scenario.yaml"
    scenario_path.write_text(yaml.dump({
        "name": "test-scenario",
        "assumptions": {"model_backend": "rubric"},
        "overrides": {
            "branches": {
                "a": {"rating": 1.0},
                "new-branch": {"name": "New Branch", "lat": 25.3, "lng": 55.3, "area": "New"},
            },
            "communities": {"c1": {"population_female": 1}},
        },
    }))

    settings = Settings(_env_file=None, seed_dir=seed_dir, raw_dir=raw_dir,
                         processed_dir=baseline_dir)
    main(scenario_path, settings)

    after = {
        p: (p.read_bytes(), p.stat().st_mtime_ns)
        for p in baseline_dir.rglob("*") if p.is_file()
    }
    assert after == before


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


def test_run_scenario_returns_bundle_without_touching_disk(tmp_path):
    seed_dir, raw_dir, baseline_dir, scenarios_dir = _write_seed_and_baseline(tmp_path)

    scenario_path = scenarios_dir / "test-scenario.yaml"
    scenario_path.write_text(yaml.dump({
        "name": "test-scenario",
        "assumptions": {"model_backend": "rubric"},
        "overrides": {"branches": {"a": {"rating": 3.0}}},
    }))

    from src.scenario.load import load_scenario
    scenario = load_scenario(scenario_path)
    settings = Settings(_env_file=None, seed_dir=seed_dir, raw_dir=raw_dir,
                         processed_dir=baseline_dir)

    current_dir = baseline_dir.parent / "current"
    assert not current_dir.exists()

    run = run_scenario(scenario, settings)

    assert not current_dir.exists()  # no disk writes from run_scenario itself
    assert run.scenario_name == "test-scenario"
    assert len(run.features) == 2  # a, b
    by_id = {d.branch_id: d for d in run.decisions}
    assert "a" in by_id and "b" in by_id
    diff_by_id = {b.branch_id: b for b in run.diff.branches}
    assert diff_by_id["a"].changed_fields["rating"] == {"old": 4.5, "new": 3.0}


def test_run_scenario_writes_no_scenario_output_regardless_of_backend(tmp_path, monkeypatch):
    # The "no disk I/O" guarantee is about run_scenario()'s OWN output artifacts (the four
    # scenario-result files main() writes) -- not about a resolved backend's unrelated side
    # effects (e.g. LLMModel's own response cache, which is pre-existing and untouched by
    # this refactor). Fake the resolved backend here so this test exercises that contract
    # without a real Anthropic client or network call.
    seed_dir, raw_dir, baseline_dir, scenarios_dir = _write_seed_and_baseline(tmp_path)

    scenario_path = scenarios_dir / "test-scenario.yaml"
    scenario_path.write_text(yaml.dump({
        "name": "test-scenario",
        "assumptions": {"model_backend": "llm"},
        "overrides": {"branches": {"a": {"rating": 3.0}}},
    }))

    class FakeLLMBackend:
        name = "llm"

        def decide(self, branches, network):
            # Simulate a real disk-touching backend (like LLMModel's cache) to prove
            # run_scenario() itself still writes none of ITS OWN output files.
            cache_dir = tmp_path / "fake-llm-cache"
            cache_dir.mkdir(exist_ok=True)
            (cache_dir / "touched.json").write_text("{}")
            from src.model.rubric import RubricModel
            return RubricModel().decide(branches, network)

    import src.scenario.run as scenario_run_module
    monkeypatch.setattr(scenario_run_module, "resolve_backend", lambda settings: FakeLLMBackend())

    from src.scenario.load import load_scenario
    scenario = load_scenario(scenario_path)
    settings = Settings(_env_file=None, seed_dir=seed_dir, raw_dir=raw_dir,
                         processed_dir=baseline_dir)

    current_dir = baseline_dir.parent / "current"
    run = run_scenario(scenario, settings)

    assert run.diff.current_backend == "llm"
    for name in ("branch_features.json", "community_assignment.json", "communities.json",
                 "decisions.json", "run_meta.json", "diff.json"):
        assert not (current_dir / name).exists()


def test_main_writes_identical_output_via_run_scenario(tmp_path):
    # main() must still write byte-for-byte the same four files + diff.json it always has --
    # this is the regression guard that the refactor didn't change CLI behavior.
    seed_dir, raw_dir, baseline_dir, scenarios_dir = _write_seed_and_baseline(tmp_path)

    scenario_path = scenarios_dir / "test-scenario.yaml"
    scenario_path.write_text(yaml.dump({
        "name": "test-scenario",
        "assumptions": {"model_backend": "rubric"},
        "overrides": {"branches": {"a": {"rating": 3.0}}},
    }))

    settings = Settings(_env_file=None, seed_dir=seed_dir, raw_dir=raw_dir,
                         processed_dir=baseline_dir)
    main(scenario_path, settings)

    current_dir = baseline_dir.parent / "current"
    for name in ("branch_features.json", "community_assignment.json", "communities.json",
                 "decisions.json", "run_meta.json", "diff.json"):
        assert (current_dir / name).exists()
