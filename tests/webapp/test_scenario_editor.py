from streamlit.testing.v1 import AppTest

SCRIPT = """
import streamlit as st

from src.models import Branch
from src.webapp.scenario_editor import (
    build_scenario, clear_overrides, render_assumptions, render_branch_override,
)

existing = {
    "a": Branch(id="a", name="Branch A", lat=25.0, lng=55.0, area="Area A",
                rating=4.5, review_count=10, avg_price_aed=99.0, source="seed"),
}

render_assumptions()
render_branch_override(existing)
if st.button("Clear", key="Clear"):
    clear_overrides()
st.session_state["_scenario"] = build_scenario()
"""


def test_assumptions_default_to_rubric_and_baseline_contest_ratio():
    at = AppTest.from_string(SCRIPT)
    at.run()
    scenario = at.session_state["_scenario"]
    assert scenario.assumptions.model_backend == "rubric"


def test_applying_an_override_updates_the_scenario():
    at = AppTest.from_string(SCRIPT)
    at.run()
    at.slider(key="rating-a").set_value(2.0).run()
    at.button(key="apply-a").click().run()
    scenario = at.session_state["_scenario"]
    assert scenario.overrides.branches["a"]["rating"] == 2.0


def test_clear_overrides_empties_the_scenario():
    at = AppTest.from_string(SCRIPT)
    at.run()
    at.slider(key="rating-a").set_value(2.0).run()
    at.button(key="apply-a").click().run()
    at.button(key="Clear").click().run()
    scenario = at.session_state["_scenario"]
    assert scenario.overrides.branches == {}
