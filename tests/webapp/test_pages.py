from streamlit.testing.v1 import AppTest


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
    def run_model_page():
        from src.webapp.pages.model import render
        render()

    at = AppTest.from_function(run_model_page)
    at.run()
    assert not at.exception
    headers = [h.value for h in at.header]
    assert "Known limitations" in headers


def test_app_story_page_explains_evolution():
    def run_story_page():
        from src.webapp.pages.story import render
        render()

    at = AppTest.from_function(run_story_page)
    at.run()
    assert not at.exception
    headers = [h.value for h in at.header]
    assert "How this evolved" in headers
