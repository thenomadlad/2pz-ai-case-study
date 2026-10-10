"""Lounge page: one Bedashing lounge. The PROTECT / HOLD / SHRINK call with this lounge's caveats
beside it, the four signals on their scales, its catchment map, premium substitutes and the
lounges it shares women with."""
import streamlit as st

from src import explain
from src.features.lounges import substitutes
from src.model import scorecard
from src.webapp import data, nav
from src.webapp.map import (
    build_deck,
    catchment_cells_layer,
    flag_layer,
    lounge_layer,
    polygon_layer,
    substitutes_layer,
    view_at,
)
from src.webapp.views import (
    affluence_metrics,
    badge,
    banner,
    explanation_for,
    lounge_caveats,
    render_caveats,
    render_factor_table,
    render_pyramid,
    url_picker,
    val,
    wrapped_table,
)


def _signals(f, d) -> None:
    st.markdown("##### The four signals, on fixed scales")
    st.caption("Each signal scores 0 (worst) to 1 (best for the lounge); the composite is their "
               "weighted average (rating at half weight).")
    for s in scorecard.SIGNALS:
        score = d.scores[s.name]
        st.progress(score, text=f"**{s.label}:** {val(s.field, getattr(f, s.field))} → score "
                                f"{score:.2f} (weight {s.weight:g})")
        note = (" Thin premium market: scored neutral." if s.name == "capture" and f.thin_premium_market
                else " Missing: scored neutral." if getattr(f, s.field) is None else "")
        st.caption(f"Scale: {val(s.field, s.worst)} → 0, {val(s.field, s.best)} → 1. {s.why}{note}")
    verdict = (f"Composite **{d.composite:.2f}** → **{d.action}** (PROTECT at {scorecard.PROTECT_AT} "
               f"or more, SHRINK at {scorecard.SHRINK_AT} or less). Confidence: {d.confidence}.")
    {"PROTECT": st.success, "SHRINK": st.error}.get(d.action, st.warning)(verdict)
    st.caption(f"{scorecard.THRESHOLDS_WHY} {scorecard.FLIP_WHY}")


def _shared(r, b: str) -> None:
    """Which other open lounges reach this lounge's catchment cells, and how many women."""
    w, mine = data.women(r.levels.worker_share), set(data.catchment(r.levels, b))
    c = data.v3().catchment
    c = c[(c.level == r.levels.travel) & c.cell_id.isin(mine) & (c.branch_id != b)
          & ~c.branch_id.isin(r.closed)]
    rows = sorted(((o, sum(w[x] for x in g.cell_id)) for o, g in c.groupby("branch_id")), key=lambda t: -t[1])
    total = sum(w[x] for x in mine)
    st.markdown("##### Shared catchment")
    if not rows:
        st.caption("No other open lounge reaches any of its catchment cells.")
        return
    wrapped_table([{"Lounge": o, "Women in shared cells": f"{x:,.0f}",
                    "Share of this catchment": f"{x / total:.0%}" if total else "—"} for o, x in rows])
    cols = st.columns(4)
    for i, (o, _) in enumerate(rows):
        cols[i % 4].page_link(nav.LOUNGE, label=f"{o} →", icon="💇", query_params={"lounge": o})


def _substitutes(subs: list[dict], f, coverage: float) -> None:
    st.markdown(f"##### Premium substitutes ({len(subs)} of {f.premium_pool} premium salons in the catchment)")
    st.caption(f"The most-reviewed premium salons holding {coverage:.0%} "
               "of the catchment's premium reviews: capture is this lounge's share of their reviews "
               f"(scaled ×{f.recall_multiplier:.2f} for salons the search missed).")
    if subs:
        wrapped_table([{"Salon": s["name"], "Reviews": f"{s['review_count']:,}",
                        "Rating": s["rating"] if s["rating"] is not None else "—",
                        "Premium because": s["premium_because"]} for s in subs])


def render() -> None:
    r = data.current()
    labels = {f.branch_id: f"{f.name} · {d.action}" for f, d in zip(r.features, r.decisions)}
    wanted = st.query_params.get("lounge")
    b = url_picker("Lounge", "lounge", sorted(labels), labels.get, "lounge-pick")
    st.page_link(nav.OVERVIEW, label="Back to overview", icon="⬅️", query_params={"lounge": b})
    banner()
    if wanted in r.closed:
        st.info(f"{wanted} is closed in this what-if; showing {b}.")

    f = next(f for f in r.features if f.branch_id == b)
    d = next(d for d in r.decisions if d.branch_id == b)
    flips = r.flips.get(b)
    exp, facts = explanation_for(r, "lounge", b)
    st.header(f"Lounge: {f.name}")
    badge(d.action)
    if d.action != "NOT SCORED":
        st.caption(f"Composite {d.composite:.2f} · confidence {d.confidence} · the call changes in "
                   f"{flips} of {scorecard.COMBOS} assumption combinations")
    left, right = st.columns([3, 2])
    with left:
        render_pyramid(exp)
    with right:
        render_caveats("Caveats for this lounge" if d.action == "NOT SCORED"
                       else f"Confidence: {d.confidence}. Caveats for this lounge",
                       lounge_caveats(f, d, flips), d.confidence == "low")

    v3, minutes = data.v3(), data.minutes(r.levels)
    subs = substitutes(v3, data.assumptions(), r.levels, frozenset(r.closed), b)
    layers = [catchment_cells_layer(v3.cells, data.catchment(r.levels, b), data.women(r.levels.worker_share)),
              polygon_layer(v3.polygons[(b, minutes)], minutes, f.name), substitutes_layer(subs),
              lounge_layer(r.features, r.decisions), flag_layer(r.features)]
    st.pydeck_chart(build_deck(layers, view_at(f.lat, f.lng, 10.5)), key=f"lounge-map-{b}")
    st.caption(f"Its {minutes}-min drive polygon (midday traffic), catchment cells (darker = more "
               "women), premium substitutes (grey, sized by reviews) and every lounge. Hover for data.")

    st.markdown("##### Demand: raw and affluence-weighted")
    affluence_metrics(f.catchment_women, f.addressable_women, f.affluence_rent, f.affluence_coverage)
    if d.action != "NOT SCORED":
        _signals(f, d)
    _substitutes(subs, f, data.assumptions().competitor_coverage[r.levels.coverage])
    _shared(r, b)
    render_factor_table(exp, explain.LOUNGE_TABLE, facts)
