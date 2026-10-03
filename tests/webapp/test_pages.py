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
