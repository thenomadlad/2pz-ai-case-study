"""Lounge page: one Bedashing lounge. The PROTECT / HOLD / SHRINK call with this lounge's caveats
beside it, the two signals on their scales, its catchment map, premium substitutes and the
lounges it shares women with."""
import pandas as pd
import streamlit as st

from src import explain
from src.features.lounges import NOT_SCORED, substitutes
from src.model import growth, scorecard
from src.webapp import data, nav
from src.webapp.map import (
    build_deck,
    catchment_cells_layer,
    lounge_layer,
    polygon_layer,
    substitutes_layer,
    view_at,
)
from src.webapp.views import (
    badge,
    explanation_for,
    lounge_caveats,
    performance_line,
    render_assumptions,
    render_caveats,
    render_factor_table,
    render_pyramid,
    short,
    val,
    wrapped_table,
)


def _signals(f, d) -> None:
    st.markdown("##### The two signals, on fixed scales")
    st.caption("Each signal scores 0 (worst) to 1 (best for the lounge); the composite is their "
               "weighted average. Capture, rating and shared catchment are shown below, not scored.")
    words = {"demand": growth.demand_text(f.demand_ref, f.demand_pct, f.demand_pct_uae, f.emirate).capitalize(),
             "cost": growth.rent_text(f.rent_ratio, f.rent_pct_uae, f.emirate, growth.rent_fallback(f)).capitalize()}
    for s in scorecard.SIGNALS:
        score = d.scores[s.name]
        st.progress(score, text=f"**{s.label}:** {val(s.field, getattr(f, s.field))} → score "
                                f"{score:.2f} (weight {s.weight:g})")
        note = " Missing: scored neutral." if getattr(f, s.field) is None else ""
        st.caption(f"Scale: {val(s.field, s.worst)} → 0, {val(s.field, s.best)} → 1. {s.why}{note}")
        st.markdown(words[s.name])
    nd = explain.composite_digits(min(abs(d.composite - scorecard.PROTECT_AT), abs(d.composite - scorecard.SHRINK_AT)))
    verdict = (f"Composite **{d.composite:.{nd}f}** → **{d.action}** (PROTECT at {scorecard.PROTECT_AT} "
               f"or more, SHRINK at {scorecard.SHRINK_AT} or less). Confidence: {d.confidence}.")
    {"PROTECT": st.success, "SHRINK": st.error}.get(d.action, st.warning)(verdict)
    st.caption(f"{scorecard.THRESHOLDS_WHY} {scorecard.FLIP_WHY}")


def _shared(r, b: str) -> None:
    """Which other open, scored lounges reach this lounge's catchment cells, and how many women."""
    w, mine = data.women(r.levels.worker_share), set(data.catchment(r.levels, b))
    c = data.v3().catchment
    c = c[(c.level == r.levels.travel) & c.cell_id.isin(mine) & (c.branch_id != b)
          & ~c.branch_id.isin(r.closed) & ~c.branch_id.isin(NOT_SCORED)]
    rows = sorted(((o, sum(w[x] for x in g.cell_id)) for o, g in c.groupby("branch_id")), key=lambda t: -t[1])
    total = sum(w[x] for x in mine)
    st.markdown("##### Shared catchment")
    f = next((f for f in r.features if f.branch_id == b), None)
    if f is not None and f.absorbed_share is not None:
        st.caption(f"Cannibalisation what-if: if {b} closed, our other lounges would absorb "
                   f"{f.absorbed_share:.0%} of the {f.served_women:,.0f} women it serves; the rest go to rival "
                   "salons or to no premium salon. Shown, not scored.")
    if not rows:
        st.caption("No other open, scored lounge reaches any of its catchment cells.")
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
    if subs:   # ~10 rows tall, scrolls for the rest; click a header to sort
        st.dataframe(pd.DataFrame([{"Salon": s["name"], "Reviews": s["review_count"], "Rating": s["rating"],
                                    "Premium because": s["premium_because"]} for s in subs]),
                     hide_index=True, height=388, column_config={
                         "Reviews": st.column_config.NumberColumn(format="%d"),
                         "Rating": st.column_config.NumberColumn(format="%.1f★"),
                         "Premium because": st.column_config.TextColumn(width="large")})


WEIGHTS = {s.name: s.weight for s in scorecard.SIGNALS}


def _lounge_table(r) -> str | None:
    """The comparison table, which is also the picker: returns the selected row's lounge, if any."""
    df = pd.DataFrame([{"id": f.branch_id, "Lounge": short(f.name, f.branch_id), "Call": d.action,
                        "Emirate": f.emirate,
                        "Composite": None if f.not_scored else d.composite,
                        **{n.capitalize(): d.scores.get(n) for n in WEIGHTS},
                        "Demand pct (emirate)": None if f.not_scored else f.demand_pct,
                        "Demand pct (UAE)": None if f.not_scored else f.demand_pct_uae,
                        "Rent ratio": None if f.not_scored else f.rent_ratio,
                        "Rent pct (UAE)": None if f.not_scored else f.rent_pct_uae,
                        "Performance vs site": None if f.not_scored else f.performance_vs_site,
                        "Shared catchment": f.shared_share, "Review share": f.capture,
                        "Premium reviews per 1k women": f.premium_reviews_per_1k,
                        "Shop rent (AED/m²/yr)": f.site_rent_m2, "Women per AED 1k rent": f.women_per_rent_k,
                        "Google rating": f.rating,
                        "Reviews": f.review_count, "Confidence": "n/a" if f.not_scored else d.confidence}
                       for f, d in zip(r.features, r.decisions)]).sort_values("Composite", ascending=False).set_index("id")
    c1, c2 = st.columns(2)
    calls = c1.multiselect("Call", list(dict.fromkeys(df.Call)), key="cmp-call", placeholder="All calls")
    emirates = c2.multiselect("Emirate", sorted(df.Emirate.unique()), key="cmp-emirate", placeholder="All emirates")
    df = df[df.Call.isin(calls or df.Call) & df.Emirate.isin(emirates or df.Emirate)]
    score = st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f")
    pct = st.column_config.NumberColumn(format="percent")
    event = st.dataframe(df, hide_index=True, on_select="rerun", selection_mode="single-row", key="lounge-table",
                         column_config={
        "Composite": score, **{n.capitalize(): score for n in WEIGHTS}, "Shared catchment": pct,
        "Demand pct (emirate)": pct, "Demand pct (UAE)": pct, "Rent pct (UAE)": pct,
        "Rent ratio": st.column_config.NumberColumn(format="%.2f"),
        "Performance vs site": st.column_config.NumberColumn(format="%.1fx"),
        "Review share": pct, "Premium reviews per 1k women": st.column_config.NumberColumn(format="%.0f"),
        "Shop rent (AED/m²/yr)": st.column_config.NumberColumn(format="%.0f"),
        "Women per AED 1k rent": st.column_config.NumberColumn(format="%.0f")})
    st.caption("Select a row to show that lounge below. Click a column header to sort. Signal scores are 0-1 on fixed scales (1 = good for the "
               "lounge) and both score the site within its emirate's frozen market of competitor salon sites "
               "(demand pct = share of them it out-serves, UAE-wide where the emirate has under 50; rent ratio = their "
               "median shop rent ÷ the site's, above 1 = cheaper); the UAE columns rank the same site against all "
               "UAE salon sites (rent pct: higher = dearer). Performance vs site = women the lounge serves ÷ women a typical "
               "lounge would serve there (2.7x reads 'The model estimates this lounge is performing 2.7x compared "
               "to its site'): context, not scored; shared catchment = share of its women another open lounge also reaches; review "
               "share = its share of its premium substitutes' Google reviews; premium reviews per 1k women = "
               "catchment saturation, the growth areas' measure (shown, not scored). "
               "Shop rent is our cost; women per AED 1k assumes a 150 m² unit. Rent sources: DLD shop "
               "contracts (Dubai), ADREC district rates (Abu Dhabi), shop listings (northern emirates), "
               "else the emirate median.")
    rows = event.selection.rows
    return df.index[rows[0]] if rows else None


def render() -> None:
    r = data.baseline()
    st.title("Lounges")
    st.subheader("All lounges")
    picked = _lounge_table(r)
    st.divider()
    ids = [f.branch_id for f in sorted(r.features, key=lambda f: -(next(
        d.composite for d in r.decisions if d.branch_id == f.branch_id) or 0))]
    wanted = st.query_params.get("lounge")
    # a row click wins, then a link's ?lounge=, else the top lounge. Only known ids are used: the URL is untrusted
    b = picked or (wanted if wanted in ids else ids[0])
    st.query_params["lounge"] = b
    st.page_link(nav.PREDICTIONS, label="Show on the map", icon="🗺️", query_params={"lounge": b})

    f = next(f for f in r.features if f.branch_id == b)
    d = next(d for d in r.decisions if d.branch_id == b)
    flips = r.flips.get(b)
    exp, facts = explanation_for(r, "lounge", b)
    st.header(f"Lounge: {b.replace('-', ' ').title()}")   # some Google names are just "Bedashing Beauty Lounge"
    st.caption(f"📍 {data.address(b)} · {f.emirate} · {f.rating or 'no'}★ from {f.review_count:,} Google "
               "reviews. Services offered and price tier per lounge aren't in the data.")
    badge(d.action)
    if d.action != "NOT SCORED":
        st.caption(f"Composite {d.composite:.2f} · confidence {d.confidence} · the call changes in "
                   f"{flips} of {scorecard.COMBOS} assumption combinations")
        st.markdown(performance_line(f))
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
              lounge_layer(r.features, r.decisions)]
    st.pydeck_chart(build_deck(layers, view_at(f.lat, f.lng, 10.5)), key=f"lounge-map-{b}")
    st.caption(f"Its {minutes}-min drive polygon (midday traffic), catchment cells (darker = more "
               "women), premium substitutes (grey, sized by reviews) and every lounge. Hover for data.")

    if d.action != "NOT SCORED":
        _signals(f, d)
    render_assumptions("lounge", b)
    _substitutes(subs, f, data.assumptions().competitor_coverage[r.levels.coverage])
    _shared(r, b)
    render_factor_table(exp, explain.LOUNGE_TABLE, facts)
