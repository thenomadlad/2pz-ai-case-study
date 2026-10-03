"""Widget-based scenario authoring. Every render_* function reads/writes
st.session_state directly (Streamlit's own state-across-reruns mechanism) rather than
returning values up a call chain, since widgets themselves only exist mid-script-run.
build_scenario() is the single place that turns accumulated session_state into the
Scenario object src.scenario.run.run_scenario() actually consumes.
"""
import streamlit as st

from src.models import Branch
from src.scenario.models import Scenario, ScenarioAssumptions, ScenarioOverrides

NEW_BRANCH_LABEL = "(new hypothetical branch)"


def _init_session_state() -> None:
    st.session_state.setdefault("branch_overrides", {})
    st.session_state.setdefault("community_overrides", {})
    st.session_state.setdefault("contest_ratio", 1.25)
    st.session_state.setdefault("model_backend", "rubric")


def render_assumptions() -> None:
    _init_session_state()
    st.session_state["contest_ratio"] = st.slider(
        "Contest ratio", min_value=1.0, max_value=2.0,
        value=st.session_state["contest_ratio"], step=0.05,
        help="A community counts as 'contested' when its second-nearest branch is within "
             "this ratio of its nearest.",
    )
    backend_options = ["rubric", "llm"]
    st.session_state["model_backend"] = st.radio(
        "Decision backend", options=backend_options,
        index=backend_options.index(st.session_state["model_backend"]),
        help="rubric is free, instant, and deterministic. llm costs a real API call per "
             "branch and needs ANTHROPIC_API_KEY configured -- its cache never helps across "
             "different scenarios, so rubric is the default for perturbation runs.",
    )


def render_branch_override(existing_branches: dict[str, Branch]) -> None:
    _init_session_state()
    branch_ids = sorted(existing_branches)
    # Existing branches first so the selectbox defaults to overriding one (the common
    # case) rather than to the "add new branch" form.
    choice = st.selectbox("Branch to add or override", options=[*branch_ids, NEW_BRANCH_LABEL])

    if choice == NEW_BRANCH_LABEL:
        branch_id = st.text_input("New branch id", key="new-branch-id",
                                   placeholder="e.g. dubai-marina-new")
        name = st.text_input("Name", value="Hypothetical Branch", key="new-branch-name")
        lat = st.number_input("Latitude", value=25.2048, format="%.4f", key="new-branch-lat")
        lng = st.number_input("Longitude", value=55.2708, format="%.4f", key="new-branch-lng")
        area = st.text_input("Area", value="", key="new-branch-area")
        rating = st.slider("Rating", 0.0, 5.0, 4.0, 0.1, key="new-branch-rating")
        price = st.number_input("Avg price (AED)", value=99.0, min_value=0.0,
                                 key="new-branch-price")
        if st.button("Add branch", key="add-new-branch") and branch_id:
            st.session_state["branch_overrides"][branch_id] = {
                "name": name, "lat": lat, "lng": lng, "area": area,
                "rating": rating, "avg_price_aed": price,
            }
    else:
        current = existing_branches[choice]
        rating = st.slider("Rating", 0.0, 5.0, current.rating or 4.0, 0.1, key=f"rating-{choice}")
        price = st.number_input("Avg price (AED)", value=current.avg_price_aed or 99.0,
                                 min_value=0.0, key=f"price-{choice}")
        lat = st.number_input("Latitude", value=current.lat, format="%.4f", key=f"lat-{choice}")
        lng = st.number_input("Longitude", value=current.lng, format="%.4f", key=f"lng-{choice}")
        if st.button("Apply override", key=f"apply-{choice}"):
            st.session_state["branch_overrides"][choice] = {
                "rating": rating, "avg_price_aed": price, "lat": lat, "lng": lng,
            }


def pending_overrides_summary() -> list[str]:
    _init_session_state()
    return [f"{bid}: {patch}" for bid, patch in st.session_state["branch_overrides"].items()]


def clear_overrides() -> None:
    st.session_state["branch_overrides"] = {}
    st.session_state["community_overrides"] = {}
    st.session_state["contest_ratio"] = 1.25
    st.session_state["model_backend"] = "rubric"


def build_scenario(name: str = "live-scenario") -> Scenario:
    _init_session_state()
    return Scenario(
        name=name,
        assumptions=ScenarioAssumptions(
            contest_ratio=st.session_state["contest_ratio"],
            model_backend=st.session_state["model_backend"],
        ),
        overrides=ScenarioOverrides(
            branches=st.session_state["branch_overrides"],
            communities=st.session_state["community_overrides"],
        ),
    )
