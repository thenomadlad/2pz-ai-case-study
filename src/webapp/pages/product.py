import collections

import streamlit as st

from src import explain
from src.config import settings
from src.models import Branch
from src.scenario.run import run_scenario
from src.webapp.data import load_baseline
from src.webapp.map import (
    assignment_lines_layer,
    branch_layer,
    build_deck,
    community_layer,
    competitor_layer,
    diff_highlight_layers,
    opportunity_layer,
    sibling_lines_layer,
)
from src.webapp.scenario_editor import (
    build_scenario,
    clear_overrides,
    pending_overrides_summary,
    render_assumptions,
    render_branch_override,
)

ROIC_NEEDS = [
    ("Revenue per branch", "the branch P&L / POS system"),
    ("Rent and service charges", "lease agreements"),
    ("Fit-out capex and remaining book value", "the fixed-asset register"),
    ("Lease expiry and break clauses", "lease agreements"),
    ("Staff cost and utilisation", "payroll and booking system"),
]


def _headline(data) -> dict:
    counts = collections.Counter(d.action for d in data.decisions)
    shrink_ids = {d.branch_id for d in data.decisions if d.action == "SHRINK"}
    shrink_drivers = collections.Counter(
        driver for d in data.decisions if d.branch_id in shrink_ids for driver in d.key_drivers
    )
    opp_counts = collections.Counter(o.action for o in data.opportunities)
    return {
        "protect": counts.get("PROTECT", 0),
        "hold": counts.get("HOLD", 0),
        "shrink": counts.get("SHRINK", 0),
        "total": len(data.decisions),
        "top_shrink_drivers": [driver for driver, _ in shrink_drivers.most_common(2)],
        "grow": opp_counts.get("GROW", 0),
        "watch": opp_counts.get("WATCH", 0),
        "areas": len(data.opportunities),
    }


def _render_headline(data) -> None:
    h = _headline(data)
    st.header("The recommendation")
    st.markdown(
        f"Of **{h['total']} branches** in Bedashing's Dubai network: "
        f"**{h['protect']} PROTECT**, **{h['hold']} HOLD**, **{h['shrink']} SHRINK**. "
        f"Of **{h['areas']} Dubai communities**, **{h['grow']} are GROW** candidates for a "
        f"new branch and **{h['watch']} are WATCH**."
    )
    if h["top_shrink_drivers"]:
        drivers = " and ".join(h["top_shrink_drivers"])
        st.markdown(f"SHRINK calls are driven primarily by weak **{drivers}**.")
    st.caption(
        "Built for Bedashing's portfolio team to form recommendations, which the COO approves "
        "or questions and the PE board must find defensible. **Dubai only, by design**: it "
        "is the densest market and the only emirate with community-level population data. "
        f"Pipeline run at {data.pipeline_run_at:%Y-%m-%d %H:%M} UTC."
    )
    st.warning(
        "This scores **location and market position only**: demand, cannibalisation, "
        "competition and customer rating. There is no revenue, rent or capex data, so it "
        "cannot say anything about return on invested capital. Treat SHRINK as \"investigate "
        "first\", not \"close\"."
    )
    with st.expander("What a return-on-capital view would need"):
        st.table({"Missing input": [n for n, _ in ROIC_NEEDS],
                  "Where analysts would get it": [s for _, s in ROIC_NEEDS]})


def _explanation_cache() -> dict:
    # Committed AI explanations, plus any generated live this session (only with a key).
    if "explanation_cache" not in st.session_state:
        st.session_state["explanation_cache"] = explain.load_cache()
    return st.session_state["explanation_cache"]


def _render_explanation(kind: str, subject_id: str, action: str, facts: dict,
                        table_fields: tuple[str, ...]) -> None:
    exp = explain.explain(kind, subject_id, action, facts, cache=_explanation_cache(),
                          client=explain.make_client())
    st.markdown("**Why**")
    for i, reason in enumerate(exp.reasons, start=1):
        st.markdown(f"{i}. {reason.claim}")
        st.caption(" · ".join(f"{e.label}: {explain.fmt_unit(e.field, e.value)}"
                              for e in reason.evidence))
    st.markdown("**The factors**")
    st.caption(exp.table_caption)
    st.dataframe(explain.table_rows(table_fields, facts), hide_index=True,
                 width="stretch")
    st.caption(f"Thresholds: {exp.thresholds_note}")
    st.caption("Explanation: " + ("AI-generated (Claude), every number checked against the "
                                  "data above" if exp.source == "ai"
                                  else "template (no AI): written from fixed rules"))


def _render_branch_panel(feature, decision) -> None:
    st.subheader(feature.name)
    if decision:
        st.markdown(f"**{decision.action}** · composite {decision.composite:.2f} · "
                    f"{decision.confidence} confidence")
        _render_explanation("branch", feature.branch_id, decision.action,
                            explain.branch_facts(feature, decision), explain.BRANCH_TABLE)
        if decision.caveats:
            st.caption("Caveats: " + " ".join(decision.caveats))


def _render_opportunity_panel(community, opp) -> None:
    st.subheader(community.name)
    st.markdown(f"**{opp.action}** · {opp.rationale}")
    _render_explanation("opportunity", community.community_id, opp.action,
                        explain.opportunity_facts(community, opp), explain.OPPORTUNITY_TABLE)
    st.caption("Caveats: " + " ".join(opp.caveats))


def render() -> None:
    st.title("The Product")
    data = load_baseline(settings)
    _render_headline(data)

    st.divider()
    st.subheader("The evidence — click a branch or a community")
    st.caption("Branches: green PROTECT, amber HOLD, red SHRINK, sized by female residents "
               "served. Communities: blue GROW, purple WATCH, grey SKIP.")

    cols = st.columns(4)
    show_opportunities = cols[0].checkbox("Opportunity areas", value=True)
    show_competitors = cols[1].checkbox("Competitor salons", value=False)
    show_communities = cols[2].checkbox("Catchment colours", value=False)
    show_assignment_lines = cols[3].checkbox("Assignment lines", value=False)

    scenario_run = st.session_state.get("scenario_run")
    community_features = scenario_run.community_features if scenario_run else data.community_features
    opportunities = scenario_run.opportunities if scenario_run else data.opportunities

    decisions_by_id = {d.branch_id: d for d in data.decisions}
    branch_actions = {f.branch_id: (decisions_by_id[f.branch_id].action
                                      if f.branch_id in decisions_by_id else "HOLD")
                       for f in data.features}

    layers = []
    if show_competitors:
        layers.append(competitor_layer(data.competitors))
    if show_communities:
        layers.append(community_layer(data.communities, data.assignments, branch_actions))
    if show_opportunities:
        layers.append(opportunity_layer(community_features, opportunities))
    if show_assignment_lines:
        layers.append(assignment_lines_layer(data.communities, data.assignments, data.features))
    layers.append(branch_layer(data.features, data.decisions))
    if scenario_run:
        layers.extend(diff_highlight_layers(scenario_run.diff, data.features))

    event = st.pydeck_chart(build_deck(layers), on_select="rerun",
                             selection_mode="single-object", key="branch-map")

    objects = event.selection.get("objects", {}) if event else {}
    if objects.get("branches"):
        selected_id = objects["branches"][0]["branch_id"]
        feature = next(f for f in data.features if f.branch_id == selected_id)
        _render_branch_panel(feature, data.decision_for(selected_id))
        st.pydeck_chart(build_deck([branch_layer(data.features, data.decisions),
                                     sibling_lines_layer(feature, data.features)]))
    elif objects.get("opportunities"):
        community_id = objects["opportunities"][0]["community_id"]
        community = next(c for c in community_features if c.community_id == community_id)
        opp = next(o for o in opportunities if o.community_id == community_id)
        _render_opportunity_panel(community, opp)

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
        try:
            st.session_state["scenario_run"] = run_scenario(scenario, settings)
        except Exception as exc:  # noqa: BLE001 - surface any override/run failure as a
            # friendly message instead of a raw traceback; this is a Streamlit page
            # boundary, not library code, so a deliberately broad catch is appropriate here.
            st.error(f"Couldn't run that scenario: {exc}")
        else:
            st.rerun()
    if col2.button("Reset to baseline"):
        clear_overrides()
        st.session_state.pop("scenario_run", None)
        st.rerun()

    if scenario_run:
        st.subheader("What changed")
        changed = [b for b in scenario_run.diff.branches
                   if b.action_changed or b.changed_fields or b.old is None]
        st.write(f"{len(changed)} branch(es) changed, "
                 f"{sum(1 for c in scenario_run.diff.communities if c.reassigned)} "
                 "community(ies) reassigned.")
        for entry in changed:
            if entry.old is None:
                action_line = f"new → {entry.new['action']}"
            elif entry.action_changed:
                action_line = f"{entry.old['action']} → {entry.new['action']}"
            else:
                action_line = entry.new["action"]
            st.write(f"**{entry.branch_id}** ({action_line})", entry.changed_fields)
        baseline_opp = {o.community_id: o.action for o in data.opportunities}
        flips = [f"**{o.community_id}**: {baseline_opp.get(o.community_id, 'new')} → {o.action}"
                 for o in scenario_run.opportunities
                 if baseline_opp.get(o.community_id) != o.action]
        if flips:
            st.markdown("Opportunity areas that changed: " + "; ".join(flips))
