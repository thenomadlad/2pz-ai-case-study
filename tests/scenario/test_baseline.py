from unittest.mock import MagicMock

import yaml

from src.config import Settings
from src.scenario.baseline import load_baseline_assumptions, main


def test_load_baseline_assumptions_from_yaml(tmp_path):
    path = tmp_path / "baseline.yaml"
    path.write_text(yaml.dump({
        "assumptions": {
            "contest_ratio": 1.3,
            "global_female_share": 0.52,
            "fallback_price_aed": 110.0,
            "model_backend": "rubric",
        }
    }))

    assumptions = load_baseline_assumptions(path)

    assert assumptions.contest_ratio == 1.3
    assert assumptions.global_female_share == 0.52
    assert assumptions.fallback_price_aed == 110.0
    assert assumptions.model_backend == "rubric"


def test_load_baseline_assumptions_defaults_when_file_sparse(tmp_path):
    path = tmp_path / "baseline.yaml"
    path.write_text(yaml.dump({"assumptions": {"contest_ratio": 1.1}}))

    assumptions = load_baseline_assumptions(path)

    assert assumptions.contest_ratio == 1.1
    assert assumptions.global_female_share == 0.49  # BaselineAssumptions default


def test_main_clears_stale_current_dir(tmp_path, monkeypatch):
    # Fix 6: a stale data/processed/current/diff.json from a previous scenario run must
    # not survive a baseline regeneration -- /api/diff would otherwise keep serving a
    # comparison against a baseline that no longer exists on disk.
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "baseline.yaml").write_text(yaml.dump({
        "assumptions": {"contest_ratio": 1.4, "model_backend": "rubric"},
    }))

    processed_dir = tmp_path / "processed" / "baseline"
    test_settings = Settings(_env_file=None, seed_dir=tmp_path / "seed",
                              processed_dir=processed_dir)

    monkeypatch.setattr("src.scenario.baseline.acquire_run.main", MagicMock())
    monkeypatch.setattr("src.scenario.baseline.features_build.main", MagicMock())
    monkeypatch.setattr("src.scenario.baseline.model_run.main", MagicMock())

    main(test_settings)

    current_dir = processed_dir.parent / "current"
    current_dir.mkdir(parents=True, exist_ok=True)
    (current_dir / "diff.json").write_text("{}")
    assert (current_dir / "diff.json").exists()

    main(test_settings)

    assert not current_dir.exists()


def test_main_calls_all_three_stages_with_baseline_settings(tmp_path, monkeypatch):
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "baseline.yaml").write_text(yaml.dump({
        "assumptions": {"contest_ratio": 1.4, "model_backend": "rubric"},
    }))

    # processed_dir/raw_dir must be pinned under tmp_path -- main() now also rmtree's
    # processed_dir.parent/"current" (Fix 6), and without this override that defaults to
    # the real REPO_ROOT/data/processed/baseline, so this test would delete the real
    # repo's data/processed/current/ as a side effect.
    test_settings = Settings(_env_file=None, seed_dir=tmp_path / "seed",
                              raw_dir=tmp_path / "raw", processed_dir=tmp_path / "processed" / "baseline")

    mock_acquire = MagicMock()
    mock_features = MagicMock()
    mock_model = MagicMock()
    monkeypatch.setattr("src.scenario.baseline.acquire_run.main", mock_acquire)
    monkeypatch.setattr("src.scenario.baseline.features_build.main", mock_features)
    monkeypatch.setattr("src.scenario.baseline.model_run.main", mock_model)

    main(test_settings)

    mock_acquire.assert_called_once()
    mock_features.assert_called_once()
    mock_model.assert_called_once()
    called_settings = mock_acquire.call_args[0][0]
    assert called_settings.contest_ratio == 1.4
    assert called_settings.model_backend == "rubric"
