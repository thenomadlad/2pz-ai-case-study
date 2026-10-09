"""Widget-based scenario authoring. Every render_* function reads/writes
st.session_state directly (Streamlit's own state-across-reruns mechanism) rather than
returning values up a call chain, since widgets themselves only exist mid-script-run.
build_scenario() is the single place that turns accumulated session_state into the
Scenario object src.scenario.run.run_scenario() actually consumes.
"""
import streamlit as st

from src.config import settings as default_settings
from src.models import Branch
from src.scenario.baseline import load_baseline_assumptions
from src.scenario.models import Scenario, ScenarioAssumptions, ScenarioOverrides

# Prefixes of the per-branch widget keys render_branch_override() creates dynamically (one
# set per branch id, plus the "new branch" form) -- clear_overrides() deletes any
# session_state key starting with one of these so a reset doesn't leave a stale slider
# value behind even though branch_overrides itself is empty again.
_WIDGET_KEY_PREFIXES = ("rating-", "price-", "lat-", "lng-", "new-branch-")


def _baseline_contest_ratio() -> float:
    scenarios_dir = default_settings.seed_dir.parent / "scenarios"
    return load_baseline_assumptions(scenarios_dir / "baseline.yaml").contest_ratio


def _init_session_state() -> None:
    st.session_state.setdefault("branch_overrides", {})
    st.session_state.setdefault("community_overrides", {})
    st.session_state.setdefault("contest_ratio", _baseline_contest_ratio())
    st.session_state.setdefault("widget_reset_nonce", 0)


def render_assumptions() -> None:
    _init_session_state()
    st.session_state["contest_ratio"] = st.slider(
        "Contest ratio (cannibalisation threshold)", min_value=1.0, max_value=2.0,
        value=st.session_state["contest_ratio"], step=0.05,
        help="Cannibalisation threshold: a community counts as contested when its "
             "second-nearest branch is within this ratio of its nearest. Starts at "
             "baseline's own value -- an untouched slider means this axis isn't part of "
             "your scenario.",
    )


def _nonce() -> int:
    # Suffixed onto every value-holding widget's key below. Streamlit sliders/number_inputs
    # don't visually reset to a new `value=` just because their session_state entry was
    # deleted -- the mounted frontend component keeps its last displayed value until the
    # widget's key itself changes, which forces a real remount. clear_overrides() bumps
    # this nonce, so the widgets rendered on the NEXT run are genuinely new components
    # (observed directly: without this, "Reset to baseline" left an overridden rating
    # slider visually stuck at the overridden value even though session_state was clear).
    _init_session_state()
    return st.session_state["widget_reset_nonce"]


def render_new_branch() -> None:
    """Form for a hypothetical new branch (a network-wide what-if, on the overview)."""
    nonce = _nonce()
    branch_id = st.text_input("New branch id", key=f"new-branch-id-{nonce}",
                               placeholder="e.g. dubai-marina-new")
    name = st.text_input("Name", value="Hypothetical Branch", key=f"new-branch-name-{nonce}")
    lat = st.number_input("Latitude", value=25.2048, format="%.4f",
                           key=f"new-branch-lat-{nonce}")
    lng = st.number_input("Longitude", value=55.2708, format="%.4f",
                           key=f"new-branch-lng-{nonce}")
    area = st.text_input("Area", value="", key=f"new-branch-area-{nonce}")
    rating = st.slider("Rating", 0.0, 5.0, 4.0, 0.1, key=f"new-branch-rating-{nonce}")
    price = st.number_input("Avg price (AED)", value=99.0, min_value=0.0,
                             key=f"new-branch-price-{nonce}")
    if st.button("Add branch", key="add-new-branch") and branch_id:
        st.session_state["branch_overrides"][branch_id] = {
            "name": name, "lat": lat, "lng": lng, "area": area,
            "rating": rating, "avg_price_aed": price,
        }


def render_branch_override(current: Branch) -> None:
    """What-if form for one existing branch (on that branch's details section)."""
    nonce, bid = _nonce(), current.id
    rating = st.slider("Rating", 0.0, 5.0, current.rating or 4.0, 0.1,
                        key=f"rating-{bid}-{nonce}")
    price = st.number_input("Avg price (AED)", value=current.avg_price_aed or 99.0,
                             min_value=0.0, key=f"price-{bid}-{nonce}")
    lat = st.number_input("Latitude", value=current.lat, format="%.4f", key=f"lat-{bid}-{nonce}")
    lng = st.number_input("Longitude", value=current.lng, format="%.4f", key=f"lng-{bid}-{nonce}")
    if st.button("Apply override", key=f"apply-{bid}"):
        st.session_state["branch_overrides"][bid] = {
            "rating": rating, "avg_price_aed": price, "lat": lat, "lng": lng,
        }


def render_run_controls(key: str) -> None:
    """Pending overrides plus Run / Reset. `key` keeps button ids unique per page section."""
    from src.config import settings
    from src.scenario.run import run_scenario

    pending = pending_overrides_summary()
    if pending:
        st.write("Pending overrides:", pending)
    col1, col2 = st.columns(2)
    if col1.button("Run scenario", type="primary", key=f"run-{key}"):
        try:
            st.session_state["scenario_run"] = run_scenario(build_scenario(), settings)
        except Exception as exc:  # noqa: BLE001 - surface any override/run failure as a
            # friendly message instead of a raw traceback; this is a Streamlit page
            # boundary, not library code, so a deliberately broad catch is appropriate here.
            st.error(f"Couldn't run that scenario: {exc}")
        else:
            st.rerun()
    if col2.button("Reset to baseline", key=f"reset-{key}"):
        clear_overrides()
        st.session_state.pop("scenario_run", None)
        st.rerun()


def pending_overrides_summary() -> list[str]:
    _init_session_state()
    return [f"{bid}: {patch}" for bid, patch in st.session_state["branch_overrides"].items()]


def clear_overrides() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(_WIDGET_KEY_PREFIXES):
            del st.session_state[key]
    st.session_state["branch_overrides"] = {}
    st.session_state["community_overrides"] = {}
    st.session_state["contest_ratio"] = _baseline_contest_ratio()
    # Forces every value-holding widget in this module to remount on the next
    # run (new key = new component) instead of visually keeping its last displayed value.
    st.session_state["widget_reset_nonce"] = st.session_state.get("widget_reset_nonce", 0) + 1


def build_scenario(name: str = "live-scenario") -> Scenario:
    _init_session_state()
    return Scenario(
        name=name,
        assumptions=ScenarioAssumptions(
            contest_ratio=st.session_state["contest_ratio"],
        ),
        overrides=ScenarioOverrides(
            branches=st.session_state["branch_overrides"],
            communities=st.session_state["community_overrides"],
        ),
    )
