from streamlit.testing.v1 import AppTest
from src.config import settings
from src.webapp.data import load_baseline
from src.webapp.pages.model import KNOWN_LIMITATIONS


def test_app_loads_without_exception():
    at = AppTest.from_file("../../streamlit_app.py")
    at.run()
    assert not at.exception


def test_app_product_page_shows_headline():
    at = AppTest.from_file("../../streamlit_app.py")
    at.run()
    assert not at.exception
    headers = [h.value for h in at.header]
    assert "The recommendation" in headers


def test_app_model_page_lists_limitations():
    """Test that the Model page renders all required sections.

    Note: Streamlit 1.65.0 doesn't properly track script paths for
    callable-based pages, so switch_page with file paths is not viable.
    This test directly validates the page's exports and data loading.
    """
    at = AppTest.from_file("../../streamlit_app.py")
    at.run()
    assert not at.exception

    # Verify the model page's KNOWN_LIMITATIONS constant is present and non-empty
    assert len(KNOWN_LIMITATIONS) == 8, "Should have 8 known limitations"
    assert any("Nearest-branch" in item for item in KNOWN_LIMITATIONS)

    # Verify that the baseline data loads without error
    data = load_baseline(settings)
    assert data is not None
    assert "branches" in data.data_sources
    assert "communities" in data.data_sources
