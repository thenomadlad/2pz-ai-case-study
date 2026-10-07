from src.config import Settings


def test_defaults(monkeypatch):
    for key in ["CONTEST_RATIO", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"]:
        monkeypatch.delenv(key, raising=False)
    s = Settings(_env_file=None)
    assert s.contest_ratio == 1.25
    assert s.anthropic_api_key is None
    assert s.anthropic_model == "claude-opus-5-5"
    assert s.global_female_share == 0.49
    assert s.fallback_price_aed == 99.0
    from src.config import REPO_ROOT
    assert s.processed_dir == REPO_ROOT / "data" / "processed" / "baseline"


def test_env_override(monkeypatch):
    monkeypatch.setenv("CONTEST_RATIO", "1.1")
    s = Settings(_env_file=None)
    assert s.contest_ratio == 1.1
