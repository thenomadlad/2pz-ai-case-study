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
        import streamlit as st
        from src.webapp.pages.model import render
        render()

    at = AppTest.from_function(run_model_page)
    at.run()
    assert not at.exception
    headers = [h.value for h in at.header]
    assert "Known limitations" in headers
