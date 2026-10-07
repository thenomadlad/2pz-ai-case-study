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
    st.rerun()
st.session_state["_scenario"] = build_scenario()
"""


def test_assumptions_default_to_baseline_contest_ratio():
    from src.config import settings
    from src.scenario.baseline import load_baseline_assumptions

    at = AppTest.from_string(SCRIPT)
    at.run()
    scenario = at.session_state["_scenario"]
    baseline_yaml = settings.seed_dir.parent / "scenarios" / "baseline.yaml"
    assert scenario.assumptions.contest_ratio == load_baseline_assumptions(
        baseline_yaml).contest_ratio


def test_applying_an_override_updates_the_scenario():
    at = AppTest.from_string(SCRIPT)
    at.run()
    # Widget keys carry a reset-nonce suffix (starts at 0) so clear_overrides() can force a
    # true remount later -- see render_branch_override()'s docstring comment.
    at.slider(key="rating-a-0").set_value(2.0).run()
    at.button(key="apply-a").click().run()
    scenario = at.session_state["_scenario"]
    assert scenario.overrides.branches["a"]["rating"] == 2.0


def test_clear_overrides_empties_the_scenario():
    at = AppTest.from_string(SCRIPT)
    at.run()
    at.slider(key="rating-a-0").set_value(2.0).run()
    at.button(key="apply-a").click().run()
    at.button(key="Clear").click().run()
    scenario = at.session_state["_scenario"]
    assert scenario.overrides.branches == {}
    # The nonce must have bumped, and the newly-keyed slider must show the branch's real
    # baseline rating again -- this is the actual fix for the "slider stays visually stuck
    # after reset" bug found during browser verification, not just the override dict
    # clearing (session_state alone clearing isn't enough to fix that bug).
    assert at.slider(key="rating-a-1").value == 4.5
