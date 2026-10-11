import pytest

from src.config import settings as default_settings


@pytest.fixture(autouse=True)
def _no_real_llm_calls(monkeypatch):
    """The app never calls an API (explanations come from the committed cache or the template);
    clear the key anyway so a local .env can't make a test spend money."""
    monkeypatch.setattr(default_settings, "anthropic_api_key", None)


@pytest.fixture(scope="session", autouse=True)
def _warm_runs():
    """The served-demand model takes ~40 s for a fresh scenario (Huff what-ifs for every area), over
    AppTest's 30 s page timeout: build the baseline and the two-closed what-if once, up front."""
    from src.baseline import run
    run()
    run(closed=frozenset({"al-barsha", "city-walk"}))
