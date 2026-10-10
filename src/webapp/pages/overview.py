"""Overview: the COO's question, the executive summary and what's at stake, the limitations that matter most, the what-if panel, the map
and a short pyramid for whatever you click."""
import pandas as pd
import streamlit as st

from src.features.lounges import substitutes
from src.model import growth, scorecard
from src.webapp import data, nav
from src.webapp.map import (
    affluence_layer,
    area_cells_layer,
    build_deck,
    catchment_cells_layer,
    flag_layer,
    lounge_layer,
    overlap_layer,
    polygon_layer,
    substitutes_layer,
)
from src.webapp.pages.area import ORDER, _check
from src.webapp.scenario_editor import render_panel
from src.webapp.views import (
    area_caveats,
    badge,
    banner,
    explanation_for,
    limitations_box,
    lounge_caveats,
    render_caveats,
    render_pyramid,
)


def _selection(map_state) -> tuple[str | None, str | None]:
    """(lounge, area): a map click is written into the URL, so the selection survives the map
    redrawing and Back from a details page reopens the same panel. With no click, the URL decides."""
    objects = (map_state or {}).get("selection", {}).get("objects", {})
    if objects.get("lounges"):
        st.query_params.pop("area", None)
        st.query_params["lounge"] = objects["lounges"][0]["branch_id"]
    elif objects.get("areas"):
        st.query_params.pop("lounge", None)
        st.query_params["area"] = objects["areas"][0]["area_id"]
    return st.query_params.get("lounge"), st.query_params.get("area")


def map_layers(r, lounge: str | None, show_areas: bool, show_skip: bool, show_subs: bool,
               show_affluence: bool = False, show_overlap: bool = False, show_all_subs: bool = False) -> list:
    """Bottom to top: affluence, every catchment (overlap), growth areas, every lounge's premium
    substitutes, the selected lounge's catchment cells, polygon and substitutes, then every lounge
    and its flag."""
    v3, layers = data.v3(), []
    if show_affluence:
        layers.append(affluence_layer(v3.cells))
    if show_overlap:
        layers.append(overlap_layer(v3.cells, data.reached(r.levels, frozenset(r.closed)),
                                    data.women(r.levels.worker_share)))
    if show_all_subs:
        subs = {s["place_id"]: s for f in r.features
                for s in substitutes(v3, data.assumptions(), r.levels, frozenset(r.closed), f.branch_id)}
        layers.append(substitutes_layer(list(subs.values()), "all-substitutes"))
    if show_areas:
        layers.append(area_cells_layer(v3.cells, r.areas, r.area_decisions, show_skip))
    if lounge:
        f = next(f for f in r.features if f.branch_id == lounge)
        layers += [catchment_cells_layer(v3.cells, data.catchment(r.levels, lounge),
                                         data.women(r.levels.worker_share)),
                   polygon_layer(v3.polygons[(lounge, data.minutes(r.levels))], data.minutes(r.levels), f.name)]
        if show_subs:
            layers.append(substitutes_layer(substitutes(v3, data.assumptions(), r.levels,
                                                        frozenset(r.closed), lounge)))
    return layers + [lounge_layer(r.features, r.decisions), flag_layer(r.features)]


def _legend(r, lounge: str | None, show_affluence: bool, show_overlap: bool = False,
            show_all_subs: bool = False) -> None:
    lounges, areas = st.columns(2)
    with lounges:
        _lounge_legend()
    with areas:
        _area_legend(r)
    if show_overlap:
        st.markdown(f"**Overlap**: every lounge's {data.minutes(r.levels)}-min catchment at once; faint teal = "
                    "one lounge reaches the cell, 🟥 red = **shared** by 2+ lounges (deeper = more). "
                    "Hover a cell for which lounges.")
    if show_all_subs:
        st.markdown("**Every lounge's premium substitutes** (grey, sized by reviews): the premium salons each "
                    "lounge's capture is measured against.")
    if show_affluence:
        rent = data.rents()
        st.markdown(f"**Affluence**: 🟧 observed median household rent per cell, pale = cheap "
                    f"({rent.min() / 1000:,.0f}k AED/yr), deep orange = dear ({rent.max() / 1000:,.0f}k), "
                    f"{len(rent)} Dubai cells only (DLD rents); **uncoloured cells have no data** "
                    "and are weighted neutral.")
    if lounge:
        st.markdown(f"**{lounge}**: its {data.minutes(r.levels)}-min drive polygon, catchment cells "
                    "(darker = more women) and premium substitutes (grey, sized by reviews).")
    else:
        st.caption("Click a lounge for its catchment, or an area for its call.")


def _lounge_legend() -> None:
    st.markdown("**Lounges** (flag; circle sized by women in catchment)")
    st.markdown(f"🟢 **PROTECT**: composite ≥ {scorecard.PROTECT_AT}  \n"
                f"🟠 **HOLD**: between {scorecard.SHRINK_AT} and {scorecard.PROTECT_AT}  \n"
                f"🔴 **SHRINK**: composite ≤ {scorecard.SHRINK_AT}  \n"
                "⚪ **NOT SCORED**: the airport lounge  \n"
                "◯ **Hollow** = low confidence")
    st.caption("Composite: demand, cannibalisation, capture (weight 1 each) and rating (½), each "
               f"0-1 on a fixed scale. Low confidence: within {scorecard.LOW_MARGIN} of a line, thin market, "
               "no rating gap (missing rating or no rated substitutes), the call changes in "
               f"{scorecard.FLIP_LOW}+ of {scorecard.COMBOS} assumption combinations, or it changes when a "
               "signal weight moves ±25%.")


def _area_legend(r) -> None:
    st.markdown(f"**Growth areas** (cells beyond a {data.minutes(r.levels)}-min drive of every lounge)")
    st.markdown(f"🔵 **GROW**: ≥ {growth.GROW_MIN_WOMEN:,} addressable women, worker housing under "
                f"{growth.WORKER_CAP:.0%}, *and* under {growth.UNSATURATED_PER_1K:g} premium reviews per "
                f"1k women, with ≥ {growth.MIN_COVERAGE:.0%} of women searched  \n"
                "🟣 **WATCH**: one of the two, too little searched, big only on thin affluence data, or big "
                "but mostly worker housing  \n"
                f"⚪ **SKIP**: neither, or under {growth.SKIP_UNDER_WOMEN:,} women")


def _lounge_panel(r, b: str) -> None:
    f = next((f for f in r.features if f.branch_id == b), None)
    if f is None:
        st.caption(f"{b} is closed in this what-if." if b in r.closed else "Unknown lounge in the link.")
        return
    d = next(d for d in r.decisions if d.branch_id == b)
    exp, _ = explanation_for(r, "lounge", b)
    st.subheader(f.name)
    badge(d.action)
    left, right = st.columns([3, 2])
    with left:
        render_pyramid(exp)
        if d.key_drivers:
            st.markdown("**Top drivers:** " + " · ".join(
                f"{n} {d.scores[n]:.2f} (weight {WEIGHTS[n]:g})" for n in d.key_drivers))
            st.caption("The signals furthest from neutral, each scored 0-1 (1 = good for the lounge).")
    with right:
        render_caveats("Caveats for this lounge" if d.action == "NOT SCORED"
                       else f"Confidence: {d.confidence}. Caveats for this lounge",
                       lounge_caveats(f, d, r.flips.get(b)), d.confidence == "low")
    st.page_link(nav.LOUNGE, label="Open the lounge page →", icon="💇", query_params={"lounge": b})


def _area_panel(r, area_id: str) -> None:
    a = next((a for a in r.areas if a.area_id == area_id), None)
    if a is None:
        st.caption("That area isn't a growth area in this what-if (a lounge reaches it), or the link is wrong.")
        return
    d = next(d for d in r.area_decisions if d.area_id == area_id)
    exp, _ = explanation_for(r, "area", area_id)
    st.subheader(f"{a.name}, {a.emirate}")
    badge(d.action)
    left, right = st.columns([3, 2])
    with left:
        render_pyramid(exp)
        st.markdown(f"**The tests:** {_check(d.big_enough)} big enough ({a.addressable_women:,.0f} addressable "
                    f"women) · {_check(d.unsaturated)} unsaturated · {_check(a.data_coverage >= growth.MIN_COVERAGE)} "
                    f"searched ({a.data_coverage:.0%} of women)")
    with right:
        render_caveats(f"Confidence: {d.confidence}. Caveats for this area", area_caveats(a, d),
                       d.action != "SKIP")
    st.page_link(nav.AREA, label="Open the area page →", icon="📍", query_params={"area": area_id})


WEIGHTS = {s.name: s.weight for s in scorecard.SIGNALS}
QUESTION = "Where is my network under pressure, and where should we grow?"


def stake(r) -> dict[str, tuple[int, float]]:
    """(count, women) per call: SHRINK lounges and the women in their catchment cells another open
    lounge also reaches; PROTECT lounges and their catchment women; GROW areas' addressable women;
    WATCH areas. Women are counted once per cell, however many lounges reach it."""
    w, reached = data.women(r.levels.worker_share), data.reached(r.levels, frozenset(r.closed))
    by = {k: {d.branch_id for d in r.decisions if d.action == k} for k in ("SHRINK", "PROTECT")}
    act = {d.area_id: d.action for d in r.area_decisions}
    return {"SHRINK": (len(by["SHRINK"]), sum(w[c] for c, bs in reached.items()
                                              if len(bs) > 1 and by["SHRINK"] & set(bs))),
            "PROTECT": (len(by["PROTECT"]), sum(w[c] for c, bs in reached.items() if by["PROTECT"] & set(bs))),
            "GROW": (sum(act[a.area_id] == "GROW" for a in r.areas),
                     sum(a.addressable_women for a in r.areas if act[a.area_id] == "GROW")),
            "WATCH": (sum(act[a.area_id] == "WATCH" for a in r.areas), 0.0)}


def _at_stake(r) -> None:
    s, minutes = stake(r), data.minutes(r.levels)
    cols = st.columns(3)
    cols[0].metric(f"Under pressure: {s['SHRINK'][0]} SHRINK lounges", f"{s['SHRINK'][1]:,.0f} women")
    cols[0].caption("Women 15+ in their catchment cells that a sibling lounge also reaches: the overlap a "
                    "consolidation review would test. Investigate, don't close.")
    cols[1].metric(f"To defend: {s['PROTECT'][0]} PROTECT lounges", f"{s['PROTECT'][1]:,.0f} women")
    cols[1].caption(f"Women 15+ within a {minutes}-min drive of them.")
    cols[2].metric(f"To grow: {s['GROW'][0]} GROW areas", f"{s['GROW'][1]:,.0f} women")
    cols[2].caption(f"Addressable women beyond a {minutes}-min drive of every lounge; "
                    f"{s['WATCH'][0]} more areas on WATCH.")
    st.caption("At stake is counted in women, not money: the model has no revenue, rent or capex.")


def _lounge_table(r) -> None:
    df = pd.DataFrame([{"Lounge": f.branch_id, "Call": d.action, "Emirate": f.emirate,
                        "Composite": None if f.not_scored else d.composite,
                        **{n.capitalize(): d.scores.get(n) for n in WEIGHTS},
                        "Shared catchment": f.shared_share, "Capture share": f.capture,
                        "Premium reviews per 1k women": f.premium_reviews_per_1k, "Google rating": f.rating,
                        "Reviews": f.review_count, "Confidence": "n/a" if f.not_scored else d.confidence}
                       for f, d in zip(r.features, r.decisions)]).sort_values("Composite", ascending=False)
    c1, c2 = st.columns(2)
    calls = c1.multiselect("Call", list(dict.fromkeys(df.Call)), key="cmp-call", placeholder="All calls")
    emirates = c2.multiselect("Emirate", sorted(df.Emirate.unique()), key="cmp-emirate", placeholder="All emirates")
    df = df[df.Call.isin(calls or df.Call) & df.Emirate.isin(emirates or df.Emirate)]
    score = st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f")
    pct = st.column_config.NumberColumn(format="percent")
    st.dataframe(df, hide_index=True, column_config={
        "Composite": score, **{n.capitalize(): score for n in WEIGHTS}, "Shared catchment": pct,
        "Capture share": pct, "Premium reviews per 1k women": st.column_config.NumberColumn(format="%.0f")})
    st.caption("Click a column header to sort. Signal scores are 0-1 on fixed scales (1 = good for the "
               "lounge); shared catchment = share of its women another open lounge also reaches; capture "
               "share = its share of its premium substitutes' Google reviews; premium reviews per 1k women = "
               "catchment saturation, the growth areas' measure (shown, not scored).")


def _area_table(r) -> None:
    by_id = {a.area_id: a for a in r.areas}
    ranked = sorted((d for d in r.area_decisions if d.action != "SKIP"),
                    key=lambda d: (ORDER[d.action], -by_id[d.area_id].addressable_women))
    df = pd.DataFrame([{"Rank": i, "Area": a.name, "Emirate": a.emirate, "Call": d.action,
                        "Addressable women": round(a.addressable_women), "Worker housing": a.worker_share,
                        "Premium reviews per 1k women": a.premium_reviews_per_1k, "Searched": a.data_coverage,
                        "Nearest lounge": a.nearest_lounge_id, "km (straight line)": round(a.nearest_lounge_km, 1),
                        "Confidence": d.confidence,
                        "Why": d.rationale.split(" Nearest lounge:")[0]}
                       for i, d in enumerate(ranked, start=1) for a in [by_id[d.area_id]]])
    c1, c2 = st.columns(2)
    calls = c1.multiselect("Call", ["GROW", "WATCH"], key="cmp-area-call", placeholder="GROW and WATCH")
    emirates = c2.multiselect("Emirate", sorted(df.Emirate.unique()), key="cmp-area-emirate",
                              placeholder="All emirates")
    df = df[df.Call.isin(calls or df.Call) & df.Emirate.isin(emirates or df.Emirate)]
    pct = st.column_config.NumberColumn(format="percent")
    st.dataframe(df, hide_index=True, column_config={
        "Worker housing": pct, "Searched": pct,
        "Premium reviews per 1k women": st.column_config.NumberColumn(format="%.0f"),
        "Why": st.column_config.TextColumn(width="large")})
    st.caption("Ranked GROW first, then WATCH, each by addressable women. Why: the tests it passed or "
               "failed. SKIP areas are left out.")


def render() -> None:
    st.title("Bedashing UAE network")
    banner()
    r = data.current()
    st.markdown(f"#### {QUESTION}")
    st.subheader("Executive summary")
    render_pyramid(explanation_for(r, "uae", "uae")[0])
    _at_stake(r)
    limitations_box(r)
    render_panel()

    st.divider()
    st.subheader("The map — click a lounge or an area")
    map_key = f"uae-map-{st.session_state.get('map_nonce', 0)}"
    lounge, area_id = _selection(st.session_state.get(map_key))
    # Controls above the map and the legend below it, so the map keeps its width on narrow screens.
    c1, c2, c3, c4 = st.columns(4)
    show_areas = c1.checkbox("Growth areas", value=True)
    show_skip = c2.checkbox("…including SKIP areas", value=False, disabled=not show_areas)
    show_affluence = c3.checkbox("Affluence (Dubai rents)", value=False)
    show_overlap = c4.checkbox("All catchments (overlap)", value=False)
    c1, c2, c3, _ = st.columns(4)
    show_subs = c1.checkbox("Premium substitutes", value=True)
    show_all_subs = c2.checkbox("…of every lounge", value=False)
    # Not "Clear selection": the map's own toolbar has that button, which clears only the widget.
    if (lounge or area_id) and c3.button("Deselect"):
        st.query_params.pop("lounge", None)
        st.query_params.pop("area", None)
        st.session_state["map_nonce"] = st.session_state.get("map_nonce", 0) + 1
        st.rerun()
    open_ = {f.branch_id for f in r.features}
    layers = map_layers(r, lounge if lounge in open_ else None, show_areas, show_skip, show_subs,
                        show_affluence, show_overlap, show_all_subs)
    st.pydeck_chart(build_deck(layers), on_select="rerun", selection_mode="single-object", key=map_key)
    # Only known ids reach markdown: the URL value is untrusted.
    _legend(r, lounge if lounge in open_ else None, show_affluence, show_overlap, show_all_subs)
    if lounge:
        _lounge_panel(r, lounge)
    elif area_id:
        _area_panel(r, area_id)

    st.divider()
    st.subheader("Compare")
    lounges, areas = st.tabs(["Lounges", "Growth areas, ranked"])
    with lounges:
        _lounge_table(r)
    with areas:
        _area_table(r)
