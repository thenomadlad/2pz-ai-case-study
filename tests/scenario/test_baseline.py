from unittest.mock import MagicMock

import yaml

from src.scenario.baseline import load_baseline_assumptions, main
from src.config import Settings


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


def test_main_calls_all_three_stages_with_baseline_settings(tmp_path, monkeypatch):
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "baseline.yaml").write_text(yaml.dump({
        "assumptions": {"contest_ratio": 1.4, "model_backend": "rubric"},
    }))

    test_settings = Settings(_env_file=None, seed_dir=tmp_path / "seed")

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
