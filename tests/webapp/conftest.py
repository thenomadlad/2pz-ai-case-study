import pytest

from src.config import settings as default_settings


@pytest.fixture(autouse=True)
def _no_real_llm_calls(monkeypatch):
    """Tests in this directory exercise the real Streamlit app, which can trigger
    load_baseline()'s self-heal (src/webapp/data.py) -- running the full pipeline,
    including whatever model_backend data/scenarios/baseline.yaml specifies (currently
    "llm"). Force no API key regardless of a developer's local .env, so running this test
    suite never makes a real, paid Anthropic API call; resolve_backend's existing
    fallback-to-rubric-when-no-key behavior takes over instead.
    """
    monkeypatch.setattr(default_settings, "anthropic_api_key", None)
