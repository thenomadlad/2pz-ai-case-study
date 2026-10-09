"""Branch page: one Bedashing branch. The PROTECT/HOLD/SHRINK call, its catchment across
areas, how each signal scored on its fixed scale, and a what-if form. Links to the area it
sits in and to every area in its catchment."""
import streamlit as st

from src import explain
from src.model import rubric
from src.models import Branch
from src.webapp import nav
from src.webapp.scenario_editor import render_branch_override, render_run_controls
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


def _render_scores(feature, decision) -> None:
    st.markdown("##### How the score was built")
    st.caption("Each signal is scored on a fixed scale (0 = worst, 1 = best for the branch); "
               "the composite is their equal-weight average.")
    for signal in rubric.SIGNALS:
        value = getattr(feature, signal.field)
        score = decision.scores[signal.name]
        st.progress(score, text=f"**{signal.label}:** {explain.fmt_unit(signal.field, value)}"
                                f" → score {score:.2f}")
        worst, best = (explain.fmt_unit(signal.field, v) for v in (signal.worst, signal.best))
        st.caption(f"Scale: {worst} scores 0, {best} scores 1. {signal.why}")
    verdict = (f"Composite **{decision.composite:.2f}** → **{decision.action}** "
               f"(PROTECT at {rubric.PROTECT_AT} or more, SHRINK at {rubric.SHRINK_AT} or less). "
               f"Confidence: {decision.confidence}.")
    {"PROTECT": st.success, "SHRINK": st.error}.get(decision.action, st.warning)(verdict)
    st.caption(rubric.THRESHOLDS_WHY)


def _render_catchment_areas(data, branch_id: str) -> None:
    by_id = {c.community_id: c for c in data.community_features}
    rows = sorted((a for a in data.assignments if a.nearest_branch_id == branch_id),
                  key=lambda a: -a.female_pop)
    st.markdown(f"##### Catchment: {len(rows)} areas")
    if not rows:
        st.caption("No community is closer to this branch than to another one.")
        return
    wrapped_table([{
        "Area": by_id[a.community_id].name,
        "Women": f"{a.female_pop:,}",
        "Distance": f"{a.nearest_km:.1f} km",
        "Contested by": a.second_branch_id if a.contested else "—",
        "Area call": data.opportunity_for(a.community_id).action,
    } for a in rows])
    cols = st.columns(3)
    for i, a in enumerate(rows):
        cols[i % 3].page_link(nav.AREA, label=f"{by_id[a.community_id].name} →", icon="📍",
                              query_params={"area": a.community_id})


def render() -> None:
    data, is_scenario = current_data()
    labels = {f.branch_id: f"{f.name} · {data.decision_for(f.branch_id).action}"
              for f in data.features}
    branch_id = url_picker("Branch", "branch", sorted(labels), labels.get, "branch-pick")
    feature = next(f for f in data.features if f.branch_id == branch_id)
    decision = data.decision_for(branch_id)
    home = data.area_of(branch_id)
    cols = st.columns(2)
    cols[0].page_link(nav.OVERVIEW, label="Back to overview", icon="⬅️",
                      query_params={"branch": branch_id})
    cols[1].page_link(nav.AREA, label="The area this branch is in →", icon="📍",
                      query_params={"area": home})
    scenario_banner(is_scenario)

    facts = explain.branch_facts(feature, decision)
    exp = get_explanation("branch", branch_id, decision.action, facts)
    st.header(f"Branch: {feature.name}")
    badge(decision.action)
    st.caption(f"Composite {decision.composite:.2f} · confidence {decision.confidence}")
    render_pyramid(exp)

    rivals = render_catchment_map(data, {branch_id}, feature.lat, feature.lng,
                                  key=f"branch-map-{branch_id}")
    st.caption(f"This branch's catchment (tinted dots, a line to each), the {rivals} competitor "
               "salons in it (dark dots) and every Bedashing branch (flags). Hover any point "
               "for its data.")
    _render_catchment_areas(data, branch_id)

    _render_scores(feature, decision)
    render_factor_table(exp, explain.BRANCH_TABLE, facts)
    st.caption(SOURCES)
    st.caption("Caveats: " + " ".join(decision.caveats))

    st.markdown(f"##### What if…? Change {feature.name}")
    render_branch_override(Branch(
        id=branch_id, name=feature.name, lat=feature.lat, lng=feature.lng, area="",
        rating=feature.rating, review_count=feature.review_count,
        avg_price_aed=feature.avg_price_aed, source="seed"))
    render_run_controls(branch_id)
    render_glossary()
