import pytest

from src.config import settings as default_settings


@pytest.fixture(autouse=True)
def _no_real_llm_calls(monkeypatch):
    """The app never calls an API (explanations come from the committed cache or the template);
    clear the key anyway so a local .env can't make a test spend money."""
    monkeypatch.setattr(default_settings, "anthropic_api_key", None)
