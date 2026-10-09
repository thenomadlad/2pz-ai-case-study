import yaml

from src.config import REPO_ROOT, Settings, load_baseline_assumptions


def test_defaults(monkeypatch):
    for key in ["ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"]:
        monkeypatch.delenv(key, raising=False)
    s = Settings(_env_file=None)
    assert s.anthropic_api_key is None
    assert s.anthropic_model == "claude-opus-5-5"
    assert s.v3_dir == REPO_ROOT / "data" / "seed" / "v3"


def test_env_override(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MODEL", "some-other-model")
    assert Settings(_env_file=None).anthropic_model == "some-other-model"


def test_load_baseline_assumptions_defaults_when_file_sparse(tmp_path):
    path = tmp_path / "baseline.yaml"
    path.write_text(yaml.dump({"assumptions": {"search_recall": 0.5}}))
    a = load_baseline_assumptions(path)
    assert a.search_recall == 0.5
    assert a.travel_time_minutes["medium"] == 15  # BaselineAssumptions default
