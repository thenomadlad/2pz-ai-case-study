"""What-if explorer: the what-if panel and the full map (every lounge and growth area, optional layers)
with a short pyramid for whatever you click. The Executive Summary argues; this page lets you explore."""
import streamlit as st

from src.features.lounges import substitutes
from src.model import growth, scorecard
from src.webapp import data, nav
from src.webapp.map import (
    CAPTURED_FULL,
    CAPTURED_MIN,
    area_cells_layer,
    build_deck,
    catchment_cells_layer,
    lounge_layer,
    overlap_layer,
    polygon_layer,
    substitutes_layer,
    view_at,
)
from src.webapp.pages.area import _check
from src.webapp.scenario_editor import render_panel
from src.webapp.views import (
    area_caveats,
    badge,
    banner,
    explanation_for,
    lounge_caveats,
    performance_line,
    render_caveats,
    render_pyramid,
)

WEIGHTS = {s.name: s.weight for s in scorecard.SIGNALS}


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


def map_layers(r, lounge: str | None, show_subs: bool,
               show_overlap: bool = False, show_all_subs: bool = False) -> list:
    """Bottom to top: every catchment (overlap), growth areas, every lounge's premium
    substitutes, the selected lounge's catchment cells, polygon and substitutes, then every lounge
    as a pin."""
    v3, layers = data.v3(), []
    if show_overlap:
        layers.append(overlap_layer(v3.cells, data.reached(r.levels, frozenset(r.closed)),
                                    data.women(r.levels.worker_share)))
    if show_all_subs:
        subs = {s["place_id"]: s for f in r.features
                for s in substitutes(v3, data.assumptions(), r.levels, frozenset(r.closed), f.branch_id)}
        layers.append(substitutes_layer(list(subs.values()), "all-substitutes"))
    layers.append(area_cells_layer(v3.cells, r.areas, r.area_decisions))   # always: colour says what each is
    if lounge:
        f = next(f for f in r.features if f.branch_id == lounge)
        layers += [catchment_cells_layer(v3.cells, data.catchment(r.levels, lounge),
                                         data.women(r.levels.worker_share)),
                   polygon_layer(v3.polygons[(lounge, data.minutes(r.levels))], data.minutes(r.levels), f.name)]
        if show_subs:
            layers.append(substitutes_layer(substitutes(v3, data.assumptions(), r.levels,
                                                        frozenset(r.closed), lounge)))
    return layers + [lounge_layer(r.features, r.decisions)]


LEGEND_TITLE = ("Legend · lounges: :green[**PROTECT**] :orange[**HOLD**] :red[**SHRINK**] (hollow = low confidence) · "
                "areas: :blue[**GROW**] :green[**captured**] :violet[WATCH] :gray[SKIP]")

# name -> (lat, lng, zoom): the map jumps here; "UAE" is the whole-country view
CITIES = {"UAE": (24.75, 54.95, 7.2), "Abu Dhabi": (24.42, 54.47, 9.2), "Dubai": (25.12, 55.25, 9.3),
          "Sharjah": (25.33, 55.45, 9.8), "Ajman": (25.41, 55.50, 10.6), "Umm Al Quwain": (25.54, 55.62, 10.2),
          "Ras Al Khaimah": (25.74, 55.95, 9.6), "Fujairah": (25.13, 56.33, 10.0), "Al Ain": (24.20, 55.72, 9.6),
          "Al Dhafra": (23.66, 53.70, 8.6)}


def _legend(r, lounge: str | None, show_overlap: bool = False,
            show_all_subs: bool = False) -> None:
    with st.expander(LEGEND_TITLE):
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
                    "lounge's review share is measured against.")
    if lounge:
        st.markdown(f"**{lounge}**: its {data.minutes(r.levels)}-min drive polygon, catchment cells "
                    "(darker = more women) and premium substitutes (grey, sized by reviews).")
    else:
        st.caption("Click a lounge for its catchment, or an area for its call.")


def _lounge_legend() -> None:
    st.markdown("**Lounges** (pin in the call's colour)")
    st.markdown(f"🟢 **PROTECT**: composite ≥ {scorecard.PROTECT_AT}  \n"
                f"🟠 **HOLD**: between {scorecard.SHRINK_AT} and {scorecard.PROTECT_AT}  \n"
                f"🔴 **SHRINK**: composite ≤ {scorecard.SHRINK_AT}  \n"
                "⚪ **NOT SCORED**: the airport lounge  \n"
                "◯ **Hollow** = low confidence")
    st.caption("Composite: site demand (share of its emirate's competitor salon sites a typical lounge there would out-serve) "
               "and site rent (its emirate's median salon-site rent ÷ its own), weight 1 each, each "
               f"0-1 on a fixed scale against a frozen reference; review share, rating and shared catchment are shown, not scored. Low confidence: within {scorecard.LOW_MARGIN} of a line, the call changes in "
               f"{scorecard.FLIP_LOW}+ of {scorecard.COMBOS} assumption combinations, or it changes when a "
               "signal weight moves ±25%.")


def _area_legend(r) -> None:
    st.markdown("**Areas** (every named place; colour, not checkboxes, says what each is)")
    st.markdown(f"🟦 **GROW**: a typical new lounge here would add ≥ {growth.NEW_SITE_MIN:,} net new women, "
                f"worker housing under {growth.WORKER_CAP:.0%}, out-serving {growth.DEMAND_PCT_MIN:.0%}+ of its emirate's "
                "salon sites *and* rent no dearer than their median (or unknown)  \n"
                f"🟩 **Already captured**: our lounges serve {CAPTURED_MIN:.0%}+ of its women (model estimate); "
                f"deeper green = more, deepest at {CAPTURED_FULL:.0%}+  \n"
                "🟪 **WATCH**: big but dearer or weaker demand, or mostly worker housing  \n"
                f"⬜ **SKIP or no data**: under {growth.SKIP_UNDER_WOMEN:,} women, a non-residential name, or too small a gain")

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
        if d.action != "NOT SCORED":
            st.markdown(performance_line(f))
    with right:
        render_caveats("Caveats for this lounge" if d.action == "NOT SCORED"
                       else f"Confidence: {d.confidence}. Caveats for this lounge",
                       lounge_caveats(f, d, r.flips.get(b)), d.confidence == "low")
    st.page_link(nav.LOUNGE, label=f"Open the lounge page{' (baseline)' if data.active() else ''} →", icon="💇", query_params={"lounge": b})


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
        st.markdown(f"**The tests:** {_check(d.big_enough)} big enough ({a.new_site_net or 0:,.0f} net new "
                    f"women, line {growth.NEW_SITE_MIN:,}) · "
                    f"{_check(a.demand_pct is None or a.demand_pct >= growth.DEMAND_PCT_MIN)} "
                    f"{growth.demand_text(a.demand_ref, a.demand_pct, a.demand_pct_uae, a.emirate)} · "
                    f"{_check(growth.rent_ok(a))} "
                    f"{growth.rent_text(a.rent_ratio, a.rent_pct_uae, a.emirate, growth.rent_fallback(a))} · {_check(a.data_coverage >= growth.MIN_COVERAGE)} searched ({a.data_coverage:.0%} of women)")
    with right:
        render_caveats(f"Confidence: {d.confidence}. Caveats for this area", area_caveats(a, d),
                       d.action != "SKIP")
    st.page_link(nav.AREA, label=f"Open the area page{' (baseline)' if data.active() else ''} →", icon="📍", query_params={"area": area_id})


def render() -> None:
    st.title("What-if explorer")
    banner()
    r = data.current()
    st.caption("Change the model's assumptions or close lounges and watch the calls move, then click a lounge or "
               "an area on the map. **Only this page changes:** the Executive Summary, Lounges and Areas pages "
               "always show the baseline. Every number is the model's estimate.")
    render_panel()
    st.markdown("##### The map: click a lounge or an area")
    city = st.pills("Jump to", list(CITIES), default="UAE", key="map-city") or "UAE"
    # the city is in the key: a new key is a new map, so deck.gl takes the new initial view
    map_key = f"uae-map-{st.session_state.get('map_nonce', 0)}-{city}"
    lounge, area_id = _selection(st.session_state.get(map_key))
    # Controls above the map and the legend below it, so the map keeps its width on narrow screens.
    c1, c2, c4, c5 = st.columns(4)
    show_subs = c1.checkbox("Premium substitutes", value=True)
    show_all_subs = c2.checkbox("…of every lounge", value=False)
    show_overlap = c4.checkbox("All catchments (overlap)", value=False)
    # Not "Clear selection": the map's own toolbar has that button, which clears only the widget.
    if (lounge or area_id) and c5.button("Deselect"):
        st.query_params.pop("lounge", None)
        st.query_params.pop("area", None)
        st.session_state["map_nonce"] = st.session_state.get("map_nonce", 0) + 1
        st.rerun()
    open_ = {f.branch_id for f in r.features}
    layers = map_layers(r, lounge if lounge in open_ else None, show_subs,
                        show_overlap, show_all_subs)
    lat, lng, zoom = CITIES[city]
    st.pydeck_chart(build_deck(layers, view_at(lat, lng, zoom)), on_select="rerun", selection_mode="single-object", key=map_key)
    # Only known ids reach markdown: the URL value is untrusted.
    _legend(r, lounge if lounge in open_ else None, show_overlap, show_all_subs)
    if lounge:
        _lounge_panel(r, lounge)
    elif area_id:
        _area_panel(r, area_id)
