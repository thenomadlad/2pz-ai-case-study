"""Overview: the executive summary (answer, ranked arguments, data), the map, and a short
pyramid for whatever you click, with a link to dig into its details."""
import streamlit as st

from src import explain
from src.config import settings
from src.model import opportunity, rubric
from src.webapp import nav
from src.webapp.data import load_baseline
from src.webapp.map import (
    assignment_lines_layer,
    branch_layer,
    build_deck,
    community_layer,
    competitor_layer,
    diff_highlight_layers,
    flag_layer,
    opportunity_layer,
)
from src.webapp.scenario_editor import render_assumptions, render_new_branch, render_run_controls
from src.webapp.views import (
    badge,
    current_data,
    get_explanation,
    render_how_to_read,
    render_pyramid,
    scenario_banner,
)


def _render_summary(data) -> None:
    facts = explain.network_facts(data.decisions, data.opportunities, data.community_features,
                                  len(data.competitors))
    st.subheader("Executive summary")
    render_pyramid(get_explanation("network", explain.NETWORK_ID, explain.NETWORK_ACTION, facts))


def _selection(map_state) -> tuple[str | None, str | None]:
    """(branch_id, area_id): a map click is written into the URL, so the selection survives
    the map redrawing (a selected branch adds its catchment layers) and Back from the details
    page reopens the same panel. With no click, the URL decides."""
    objects = (map_state or {}).get("selection", {}).get("objects", {})
    if objects.get("branches"):
        st.query_params.pop("area", None)
        st.query_params["branch"] = objects["branches"][0]["branch_id"]
    elif objects.get("opportunities"):
        st.query_params.pop("branch", None)
        st.query_params["area"] = objects["opportunities"][0]["community_id"]
    return st.query_params.get("branch"), st.query_params.get("area")


def map_layers(data, selected_branch: str | None, show_opportunities: bool,
               show_competitors: bool, diff=None, baseline_features=None) -> list:
    """Bottom to top: competitors, areas, the selected branch's catchment, branches, flags."""
    layers = []
    if show_competitors:
        layers.append(competitor_layer(data.competitors))
    if show_opportunities:
        layers.append(opportunity_layer(data.community_features, data.opportunities))
    if selected_branch:
        branch_actions = {d.branch_id: d.action for d in data.decisions}
        layers.append(assignment_lines_layer(data.communities, data.assignments, data.features,
                                             branch_ids={selected_branch}))
        layers.append(community_layer(data.communities, data.assignments, branch_actions,
                                      branch_ids={selected_branch}))
    layers += [branch_layer(data.features, data.decisions), flag_layer(data.features)]
    if diff is not None:
        layers += diff_highlight_layers(diff, baseline_features)
    return layers


def _render_legend(selected_branch: str | None) -> None:
    st.markdown("**Branches**: a flag ⚑ on each, circle sized by women in catchment")
    st.markdown(f"🟢 **PROTECT**: composite ≥ {rubric.PROTECT_AT}  \n"
                f"🟠 **HOLD**: between {rubric.SHRINK_AT} and {rubric.PROTECT_AT}  \n"
                f"🔴 **SHRINK**: composite ≤ {rubric.SHRINK_AT}")
    st.caption("Composite = average of four 0-1 scores: demand, cannibalisation, competition, "
               "customer rating.")
    st.markdown("**Areas**")
    st.markdown(f"🔵 **GROW**: nearest branch over {opportunity.FAR_KM:g} km *and* under "
                f"{opportunity.UNSATURATED_PER_10K:g} rival salons per 10k women  \n"
                "🟣 **WATCH**: passes one of those two tests  \n"
                "⚪ **SKIP**: passes neither, already has a branch, or under "
                f"{opportunity.MIN_POP:,} women")
    st.markdown("⚫ **Competitor salons** (OpenStreetMap)")
    if selected_branch:
        st.markdown(f"**Catchment of {selected_branch}**: its areas, tinted in its colour, "
                    "with a line to each.")
    else:
        st.caption("Click a branch to see its catchment.")


def _render_branch_panel(data, branch_id: str) -> None:
    feature = next((f for f in data.features if f.branch_id == branch_id), None)
    decision = data.decision_for(branch_id)
    if feature is None or decision is None:
        return
    st.subheader(feature.name)
    badge(decision.action)
    render_pyramid(get_explanation("branch", branch_id, decision.action,
                                   explain.branch_facts(feature, decision)))
    st.page_link(nav.BRANCH, label="Open branch page →", icon="💇",
                 query_params={"branch": branch_id})


def _render_area_panel(data, area_id: str) -> None:
    community = next((c for c in data.community_features if c.community_id == area_id), None)
    opp = data.opportunity_for(area_id)
    if community is None or opp is None:
        return
    st.subheader(community.name)
    badge(opp.action)
    render_pyramid(get_explanation("opportunity", area_id, opp.action,
                                   explain.opportunity_facts(community, opp)))
    st.page_link(nav.AREA, label="Open area page →", icon="📍",
                 query_params={"area": area_id})


def _render_what_if(baseline) -> None:
    with st.expander("What if…? Network-wide scenarios",
                     expanded="scenario_run" in st.session_state):
        st.caption("Change the cannibalisation threshold or add a hypothetical branch. To change "
                   "an existing branch, open its branch page.")
        render_assumptions()
        st.markdown("**Add a hypothetical branch**")
        render_new_branch()
        render_run_controls("overview")

        run = st.session_state.get("scenario_run")
        if not run:
            return
        st.markdown("**What changed**")
        changed = [b for b in run.diff.branches
                   if b.action_changed or b.changed_fields or b.old is None]
        st.write(f"{len(changed)} branch(es) changed, "
                 f"{sum(1 for c in run.diff.communities if c.reassigned)} "
                 "community(ies) reassigned.")
        for entry in changed:
            if entry.old is None:
                action_line = f"new → {entry.new['action']}"
            elif entry.action_changed:
                action_line = f"{entry.old['action']} → {entry.new['action']}"
            else:
                action_line = entry.new["action"]
            st.write(f"**{entry.branch_id}** ({action_line})", entry.changed_fields)
        baseline_opp = {o.community_id: o.action for o in baseline.opportunities}
        flips = [f"**{o.community_id}**: {baseline_opp.get(o.community_id, 'new')} → {o.action}"
                 for o in run.opportunities if baseline_opp.get(o.community_id) != o.action]
        if flips:
            st.markdown("Opportunity areas that changed: " + "; ".join(flips))


def render() -> None:
    st.title("Bedashing Dubai network")
    data, is_scenario = current_data()
    baseline = load_baseline(settings)
    scenario_banner(is_scenario)
    _render_summary(data)
    render_how_to_read()

    st.divider()
    st.subheader("The map — click a branch or an area")
    map_key = f"branch-map-{st.session_state.get('map_nonce', 0)}"
    branch_id, area_id = _selection(st.session_state.get(map_key))

    map_col, side = st.columns([3, 1])
    with side:
        show_opportunities = st.checkbox("Opportunity areas", value=True)
        show_competitors = st.checkbox("Competitor salons", value=False)
        # Not "Clear selection": the map's own toolbar has a button with that name, which only
        # clears the map widget, not the selection carried in the URL.
        if (branch_id or area_id) and st.button("Deselect"):
            st.query_params.pop("branch", None)
            st.query_params.pop("area", None)
            st.session_state["map_nonce"] = st.session_state.get("map_nonce", 0) + 1
            st.rerun()
        _render_legend(branch_id)
    with map_col:
        diff = st.session_state["scenario_run"].diff if is_scenario else None
        layers = map_layers(data, branch_id, show_opportunities, show_competitors,
                            diff, baseline.features)
        st.pydeck_chart(build_deck(layers), on_select="rerun", selection_mode="single-object",
                        key=map_key)
    if branch_id:
        _render_branch_panel(data, branch_id)
    elif area_id:
        _render_area_panel(data, area_id)

    st.divider()
    _render_what_if(baseline)
