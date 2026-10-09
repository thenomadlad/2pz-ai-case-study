"""Rendering pieces shared by the Overview and Details pages."""
import pandas as pd
import streamlit as st

from src import explain
from src.config import settings
from src.models import Explanation
from src.webapp.data import BaselineData, load_baseline

BADGE_COLORS = {"PROTECT": "green", "HOLD": "orange", "SHRINK": "red",
                "GROW": "blue", "WATCH": "violet", "SKIP": "gray"}


def current_data() -> tuple[BaselineData, bool]:
    """The numbers the user is looking at: the baseline, or the active scenario's."""
    data = load_baseline(settings)
    run = st.session_state.get("scenario_run")
    return (data.with_scenario(run), True) if run else (data, False)


def scenario_banner(is_scenario: bool) -> None:
    if is_scenario:
        st.warning("**Scenario view.** These numbers include your what-if overrides, not the "
                   "baseline. Reset to baseline from the overview's What if…? panel.")


def get_explanation(kind: str, subject_id: str, action: str, facts: dict) -> Explanation:
    # Committed AI explanations, plus any generated live this session (only with a key).
    if "explanation_cache" not in st.session_state:
        st.session_state["explanation_cache"] = explain.load_cache()
    return explain.explain(kind, subject_id, action, facts,
                           cache=st.session_state["explanation_cache"],
                           client=explain.make_client())


def badge(action: str) -> None:
    st.badge(action, color=BADGE_COLORS.get(action, "gray"))


def render_pyramid(exp: Explanation) -> None:
    """Answer first, then each ranked argument with its data points."""
    st.markdown(f"**{exp.headline}**")
    for i, reason in enumerate(exp.reasons, start=1):
        label = explain.TOPIC_LABELS.get(reason.topic, reason.topic)
        st.markdown(f"{i}. **{label}.** {reason.claim}")
        st.caption(" · ".join(f"{e.label}: {explain.fmt_unit(e.field, e.value)}"
                              for e in reason.evidence))
    st.caption("Written by Claude; every number checked against the data."
               if exp.source == "ai" else "Template explanation (no AI): written from fixed rules.")


def wrapped_table(rows: list[dict]) -> None:
    """A static table that wraps long text instead of scrolling it; the first column labels
    the rows."""
    df = pd.DataFrame(rows)
    st.table(df.set_index(df.columns[0]))


def render_factor_table(exp: Explanation, fields: tuple[str, ...], facts: dict) -> None:
    st.caption(exp.table_caption)
    wrapped_table(explain.table_rows(fields, facts, exp.kind))


def render_how_to_read() -> None:
    st.info(
        "**How to read this · where not to trust it**\n\n"
        "- **Who it's for:** Bedashing's portfolio team forms the calls; the COO approves or "
        "questions them; the PE board needs them defensible.\n"
        "- **Dubai only, by design:** 9 of 23 UAE branches; the only emirate with "
        "community-level population data.\n"
        "- **Location and market only:** no revenue, rent or capex data, so nothing here is a "
        "return-on-capital call. Treat SHRINK as *investigate first*, not *close*.\n"
        "- **Estimates:** female population is a uniform 49% of census figures; competitor "
        "counts come from OpenStreetMap and are a lower bound.\n"
        "- **Catchments are straight-line:** each community goes to its nearest branch, "
        "ignoring roads, malls and habit."
    )
    with st.expander("What a return-on-invested-capital view would need"):
        wrapped_table([{"Missing input": name, "Where analysts would get it": source}
                       for name, source in ROIC_NEEDS])


ROIC_NEEDS = [
    ("Revenue per branch", "the branch P&L / POS system"),
    ("Rent and service charges", "lease agreements"),
    ("Fit-out capex and remaining book value", "the fixed-asset register"),
    ("Lease expiry and break clauses", "lease agreements"),
    ("Staff cost and utilisation", "payroll and booking system"),
]


def url_picker(label: str, param: str, options: list[str], format_func, key: str) -> str:
    """A selectbox driven by ?param=. The URL is the source of truth: the keyed widget is set
    from it before rendering and writes back only on a real user change. (An unkeyed
    selectbox with a moving `index` gets a new identity, and a stale value from an earlier
    visit could overwrite the URL.)"""
    wanted = st.query_params.get(param)
    st.session_state[key] = wanted if wanted in options else options[0]

    def _picked() -> None:
        st.query_params[param] = st.session_state[key]

    return st.selectbox(label, options, key=key, on_change=_picked, format_func=format_func)


def render_catchment_map(data, catchment_of: set[str], lat: float, lng: float, key: str,
                         area=None) -> int:
    """The catchment of `catchment_of` (tinted communities, a line to each), the competitor
    salons in it, optionally one highlighted area, and every branch with its flag. Display
    only: hover for each point's data. Returns how many competitors it shows."""
    from src.features.assign import competitor_community
    from src.webapp.map import (
        area_view,
        assignment_lines_layer,
        branch_layer,
        build_deck,
        community_layer,
        competitor_layer,
        flag_layer,
        opportunity_layer,
    )

    shown = {a.community_id for a in data.assignments if a.nearest_branch_id in catchment_of}
    if area is not None:
        shown.add(area.community_id)
    counted_in = competitor_community(data.competitors, data.communities)
    rivals = [k for k in data.competitors if counted_in.get(k.id) in shown]
    actions = {d.branch_id: d.action for d in data.decisions}
    layers = [
        competitor_layer(rivals),
        assignment_lines_layer(data.communities, data.assignments, data.features, catchment_of),
        community_layer(data.communities, data.assignments, actions, catchment_of),
    ]
    if area is not None:
        layers.append(opportunity_layer([area], [data.opportunity_for(area.community_id)]))
    layers += [branch_layer(data.features, data.decisions), flag_layer(data.features)]
    st.pydeck_chart(build_deck(layers, area_view(lat, lng, 12)), key=key)
    return len(rivals)


def render_glossary() -> None:
    with st.expander("Glossary: every factor shown in the app"):
        wrapped_table([{"Factor": f.label, "Unit": f.unit, "What it means": f.meaning}
                       for f in explain.GLOSSARY.values()])


SOURCES = ("Sources: female residents are 49% of the Dubai Statistics Center census (an "
           "estimate); competitor salons are from OpenStreetMap (a lower bound); ratings are "
           "from 2GIS; all distances are straight-line.")
