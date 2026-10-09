"""Area page: one Dubai community. What's there (women, competitors, Bedashing branches),
what's left (salon headroom, uncovered women, fair-share capture), the GROW/WATCH/SKIP call
and how it was made. Links to the branches in it and to the branch whose catchment it's in."""
import streamlit as st

from src import explain
from src.features.assign import competitor_community
from src.model import opportunity
from src.webapp import nav
from src.webapp.views import (
    SOURCES,
    badge,
    current_data,
    get_explanation,
    render_catchment_map,
    render_factor_table,
    render_glossary,
    render_pyramid,
    scenario_banner,
    url_picker,
    wrapped_table,
)

ACTION_ORDER = {"GROW": 0, "WATCH": 1, "SKIP": 2}
KINDS = {"beauty": "Beauty salon", "hairdresser": "Hair salon"}


def _check(passed: bool) -> str:
    return "✅" if passed else "❌"


def _render_summary(community, opp) -> None:
    cols = st.columns(4)
    cols[0].metric("Room for more salons", opp.salon_headroom,
                   help=f"Could support about {opp.salons_supported:g} salons at the Dubai "
                        f"median of {opportunity.MEDIAN_SALONS_PER_10K:g} per 10k women; has "
                        f"{community.competitors} competitors and {community.branches_here} "
                        "Bedashing branches.")
    cols[1].metric("Women not covered by Bedashing", f"{opp.uncovered_women:,}",
                   help=f"All {community.female_pop:,} women count as uncovered when the "
                        f"nearest branch is over {opportunity.FAR_KM:g} km away.")
    cols[2].metric("Bedashing fair share", f"{opp.fair_share:.0%}",
                   help=f"About {opp.captured_women_est:,} women. Naive estimate: Bedashing's "
                        "share of the salons here, as if every salon were equally attractive.")
    cols[3].metric("Competitor salons", community.competitors,
                   help=f"{community.competitors_per_10k:.1f} per 10k women")


def _render_catchment(data, community) -> None:
    assignment = next(a for a in data.assignments if a.community_id == community.community_id)
    line = (f"In the catchment of **{assignment.nearest_branch_id}**, "
            f"{assignment.nearest_km:.1f} km away.")
    if assignment.contested:
        line += (f" Contested: **{assignment.second_branch_id}** is almost as close "
                 f"({assignment.second_km:.1f} km).")
    st.markdown(line)
    located_here = {f.branch_id for f in data.branches_in(community.community_id)}
    names = {f.branch_id: f.name for f in data.features}
    for branch_id in dict.fromkeys([assignment.nearest_branch_id, *sorted(located_here)]):
        tags = [tag for tag, applies in (("located here", branch_id in located_here),
                                         ("catchment branch",
                                          branch_id == assignment.nearest_branch_id))
                if applies]
        st.page_link(nav.BRANCH, label=f"{names[branch_id]} ({', '.join(tags)}) →",
                     icon="💇", query_params={"branch": branch_id})


def render() -> None:
    data, is_scenario = current_data()
    options = sorted(
        (c.community_id for c in data.community_features),
        key=lambda a: (ACTION_ORDER[data.opportunity_for(a).action], a))
    names = {c.community_id: c.name for c in data.community_features}
    area_id = url_picker("Area", "area", options,
                         lambda a: f"{names[a]} · {data.opportunity_for(a).action}", "area-pick")
    st.page_link(nav.OVERVIEW, label="Back to overview", icon="⬅️",
                 query_params={"area": area_id})
    scenario_banner(is_scenario)

    community = next(c for c in data.community_features if c.community_id == area_id)
    opp = data.opportunity_for(area_id)
    facts = explain.opportunity_facts(community, opp)
    exp = get_explanation("opportunity", area_id, opp.action, facts)

    st.header(f"Area: {community.name}")
    badge(opp.action)
    _render_summary(community, opp)
    render_pyramid(exp)

    catchment_of = ({f.branch_id for f in data.branches_in(area_id)}
                    or {community.nearest_branch_id})
    rivals = render_catchment_map(data, catchment_of, community.lat, community.lng,
                                  key=f"area-map-{area_id}", area=community)
    st.caption(f"This area (larger dot), the catchment of {', '.join(sorted(catchment_of))} "
               f"(tinted dots, a line to each), the {rivals} competitor salons in it (dark "
               "dots) and every Bedashing branch (flags). Hover any point for its data.")
    _render_catchment(data, community)

    st.markdown("##### How this call was made")
    cols = st.columns(3)
    cols[0].metric("Distance to nearest branch", f"{community.nearest_branch_km:.1f} km")
    cols[0].caption(f"{_check(opp.underserved)} Underserved if over {opportunity.FAR_KM:g} km")
    cols[1].metric("Competitor salons per 10k women", f"{community.competitors_per_10k:.1f}")
    cols[1].caption(f"{_check(opp.unsaturated)} Unsaturated if under "
                    f"{opportunity.UNSATURATED_PER_10K:g}")
    cols[2].metric("Female residents", f"{community.female_pop:,}")
    cols[2].caption(f"{_check(community.female_pop >= opportunity.MIN_POP)} Needs at least "
                    f"{opportunity.MIN_POP:,}")
    st.info(f"**GROW** needs both tests, **WATCH** one, **SKIP** neither. "
            f"{opportunity.THRESHOLDS_WHY}")

    render_factor_table(exp, explain.OPPORTUNITY_TABLE, facts)
    st.caption(SOURCES)
    st.caption("Caveats: " + " ".join(opp.caveats))

    counted_in = competitor_community(data.competitors, data.communities)
    here = [k for k in data.competitors if counted_in.get(k.id) == area_id]
    with st.expander(f"Competitor salons in this area ({len(here)})"):
        if here:
            wrapped_table([{"Salon": k.name or "(unnamed)", "Type": KINDS.get(k.category,
                                                                           k.category)}
                           for k in sorted(here, key=lambda k: k.name or "~")])
        else:
            st.caption("None mapped in OpenStreetMap.")
    render_glossary()
