import collections

import streamlit as st

from src.config import settings
from src.models import Branch
from src.scenario.run import run_scenario
from src.webapp.data import load_baseline
from src.webapp.map import (
    assignment_lines_layer,
    branch_layer,
    build_deck,
    community_layer,
    diff_highlight_layers,
    sibling_lines_layer,
)
from src.webapp.scenario_editor import (
    build_scenario,
    clear_overrides,
    pending_overrides_summary,
    render_assumptions,
    render_branch_override,
)


def _headline(data) -> dict:
    counts = collections.Counter(d.action for d in data.decisions)
    shrink_ids = {d.branch_id for d in data.decisions if d.action == "SHRINK"}
    shrink_drivers = collections.Counter(
        driver for d in data.decisions if d.branch_id in shrink_ids for driver in d.key_drivers
    )
    return {
        "protect": counts.get("PROTECT", 0),
        "hold": counts.get("HOLD", 0),
        "shrink": counts.get("SHRINK", 0),
        "total": len(data.decisions),
        "top_shrink_drivers": [driver for driver, _ in shrink_drivers.most_common(2)],
    }


def _render_headline(data) -> None:
    h = _headline(data)
    st.header("The recommendation")
    st.markdown(
        f"Of **{h['total']} branches** in Bedashing's Dubai network: "
        f"**{h['protect']} PROTECT**, **{h['hold']} HOLD**, **{h['shrink']} SHRINK**."
    )
    if h["top_shrink_drivers"]:
        drivers = " and ".join(h["top_shrink_drivers"])
        st.markdown(f"SHRINK calls are driven primarily by **{drivers}**.")
    st.caption(
        f"Backend: {data.model_backend} · pipeline run at "
        f"{data.pipeline_run_at:%Y-%m-%d %H:%M} UTC · "
        "every price and population figure in this dataset is an estimate, not a reported "
        "figure — see the Model page for exactly which fields and why."
    )


def _render_detail_panel(feature, decision) -> None:
    st.subheader(feature.name)
    if decision:
        st.markdown(f"**{decision.action}** ({decision.confidence} confidence)")
        st.write(decision.rationale)
        st.markdown(f"**Key drivers:** {', '.join(decision.key_drivers)}")
    st.table({
        "Feature": ["Female pop served", "Contested share", "Avg price (AED)", "Rating",
                    "Communities served"],
        "Value": [feature.female_pop_served, round(feature.contested_share, 2),
                  feature.avg_price_aed, feature.rating, feature.communities_served],
    })
    if decision and decision.caveats:
        st.caption("Caveats: " + "; ".join(decision.caveats))


def render() -> None:
    st.title("The Product")
    data = load_baseline(settings)
    _render_headline(data)

    st.divider()
    st.subheader("The evidence — stress-test the assumptions yourself")

    show_communities = st.checkbox("Show communities", value=True)
    show_assignment_lines = st.checkbox("Show assignment lines", value=False)

    branch_actions = {f.branch_id: (data.decision_for(f.branch_id).action
                                      if data.decision_for(f.branch_id) else "HOLD")
                       for f in data.features}

    layers = [branch_layer(data.features, data.decisions)]
    if show_communities:
        layers.append(community_layer(data.communities, data.assignments, branch_actions))
    if show_assignment_lines:
        layers.append(assignment_lines_layer(data.communities, data.assignments, data.features))

    scenario_run = st.session_state.get("scenario_run")
    if scenario_run:
        layers.extend(diff_highlight_layers(scenario_run.diff, data.features))

    event = st.pydeck_chart(build_deck(layers), on_select="rerun",
                             selection_mode="single-object", key="branch-map")

    selected_id = None
    objects = event.selection.get("objects", {}) if event else {}
    if objects.get("branches"):
        selected_id = objects["branches"][0]["branch_id"]

    if selected_id:
        feature = next(f for f in data.features if f.branch_id == selected_id)
        _render_detail_panel(feature, data.decision_for(selected_id))
        st.pydeck_chart(build_deck([branch_layer(data.features, data.decisions),
                                     sibling_lines_layer(feature, data.features)]))

    st.divider()
    st.subheader("Build a scenario")
    render_assumptions()
    existing_branches = {f.branch_id: Branch(id=f.branch_id, name=f.name, lat=f.lat, lng=f.lng,
                                              area="", rating=f.rating,
                                              review_count=f.review_count,
                                              avg_price_aed=f.avg_price_aed, source="seed")
                          for f in data.features}
    render_branch_override(existing_branches)

    pending = pending_overrides_summary()
    if pending:
        st.write("Pending overrides:", pending)

    col1, col2 = st.columns(2)
    if col1.button("Run scenario", type="primary"):
        scenario = build_scenario()
        st.session_state["scenario_run"] = run_scenario(scenario, settings)
        st.rerun()
    if col2.button("Reset to baseline"):
        clear_overrides()
        st.session_state.pop("scenario_run", None)
        st.rerun()

    if scenario_run:
        st.subheader("What changed")
        changed = [b for b in scenario_run.diff.branches if b.changed_fields or b.old is None]
        st.write(f"{len(changed)} branch(es) changed, "
                 f"{sum(1 for c in scenario_run.diff.communities if c.reassigned)} "
                 "community(ies) reassigned.")
        for entry in changed:
            st.write(f"**{entry.branch_id}**", entry.changed_fields)
