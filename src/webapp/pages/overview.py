"""Overview: the executive summary, the limitations that matter most, the what-if panel, the map
and a short pyramid for whatever you click."""
import streamlit as st

from src.features.lounges import substitutes
from src.model import growth, scorecard
from src.webapp import data, nav
from src.webapp.map import (
    area_cells_layer,
    build_deck,
    catchment_cells_layer,
    flag_layer,
    lounge_layer,
    polygon_layer,
    substitutes_layer,
)
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


def map_layers(r, lounge: str | None, show_areas: bool, show_skip: bool, show_subs: bool) -> list:
    """Bottom to top: growth areas, the selected lounge's catchment cells, polygon and substitutes,
    then every lounge and its flag."""
    v3, layers = data.v3(), []
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


def _legend(r, lounge: str | None) -> None:
    st.markdown("**Lounges** (flag; circle sized by women in catchment)")
    st.markdown(f"🟢 **PROTECT**: composite ≥ {scorecard.PROTECT_AT}  \n"
                f"🟠 **HOLD**: between {scorecard.SHRINK_AT} and {scorecard.PROTECT_AT}  \n"
                f"🔴 **SHRINK**: composite ≤ {scorecard.SHRINK_AT}  \n"
                "⚪ **NOT SCORED**: the airport lounge  \n"
                "◯ **Hollow** = low confidence")
    st.caption("Composite: demand, cannibalisation, capture (weight 1 each) and rating (½), each "
               f"0-1 on a fixed scale. Low confidence: within {scorecard.LOW_MARGIN} of a line, thin market, "
               "no rating gap (missing rating or no rated substitutes), or the call changes in "
               f"{scorecard.FLIP_LOW}+ of 27 assumption combinations.")
    st.markdown(f"**Growth areas** (cells beyond a {data.minutes(r.levels)}-min drive of every lounge)")
    st.markdown(f"🔵 **GROW**: ≥ {growth.GROW_MIN_WOMEN:,} women, worker housing under "
                f"{growth.WORKER_CAP:.0%}, *and* under {growth.UNSATURATED_PER_1K:g} premium reviews per "
                f"1k women, with ≥ {growth.MIN_COVERAGE:.0%} of women searched  \n"
                "🟣 **WATCH**: one of the two, too little searched, or big but mostly worker housing  \n"
                f"⚪ **SKIP**: neither, or under {growth.SKIP_UNDER_WOMEN:,} women")
    if lounge:
        st.markdown(f"**{lounge}**: its {data.minutes(r.levels)}-min drive polygon, catchment cells "
                    "(darker = more women) and premium substitutes (grey, sized by reviews).")
    else:
        st.caption("Click a lounge for its catchment, or an area for its call.")


def _lounge_panel(r, b: str) -> None:
    f = next((f for f in r.features if f.branch_id == b), None)
    if f is None:
        st.caption(f"{b} is closed in this what-if." if b in r.closed else f"Unknown lounge id: {b}.")
        return
    d = next(d for d in r.decisions if d.branch_id == b)
    exp, _ = explanation_for(r, "lounge", b)
    st.subheader(f.name)
    badge(d.action)
    left, right = st.columns([3, 2])
    with left:
        render_pyramid(exp)
    with right:
        render_caveats(f"Confidence: {d.confidence}. Caveats for this lounge",
                       lounge_caveats(f, d, r.flips.get(b)), d.confidence == "low")
    st.page_link(nav.LOUNGE, label="Open the lounge page →", icon="💇", query_params={"lounge": b})


def _area_panel(r, area_id: str) -> None:
    a = next((a for a in r.areas if a.area_id == area_id), None)
    if a is None:
        st.caption(f"{area_id} is not a growth area in this what-if (a lounge reaches it).")
        return
    d = next(d for d in r.area_decisions if d.area_id == area_id)
    exp, _ = explanation_for(r, "area", area_id)
    st.subheader(f"{a.name}, {a.emirate}")
    badge(d.action)
    left, right = st.columns([3, 2])
    with left:
        render_pyramid(exp)
    with right:
        render_caveats("Caveats for this area", area_caveats(a, d), d.action != "SKIP")
    st.page_link(nav.AREA, label="Open the area page →", icon="📍", query_params={"area": area_id})


def render() -> None:
    st.title("Bedashing UAE network")
    banner()
    r = data.current()
    st.subheader("Executive summary")
    render_pyramid(explanation_for(r, "uae", "uae")[0])
    limitations_box(r)
    render_panel()

    st.divider()
    st.subheader("The map — click a lounge or an area")
    map_key = f"uae-map-{st.session_state.get('map_nonce', 0)}"
    lounge, area_id = _selection(st.session_state.get(map_key))
    map_col, side = st.columns([3, 1])
    with side:
        show_areas = st.checkbox("Growth areas", value=True)
        show_skip = st.checkbox("…including SKIP areas", value=False, disabled=not show_areas)
        show_subs = st.checkbox("Selected lounge's premium substitutes", value=True)
        # Not "Clear selection": the map's own toolbar has that button, which clears only the widget.
        if (lounge or area_id) and st.button("Deselect"):
            st.query_params.pop("lounge", None)
            st.query_params.pop("area", None)
            st.session_state["map_nonce"] = st.session_state.get("map_nonce", 0) + 1
            st.rerun()
        _legend(r, lounge)
    with map_col:
        open_ = {f.branch_id for f in r.features}
        layers = map_layers(r, lounge if lounge in open_ else None, show_areas, show_skip, show_subs)
        st.pydeck_chart(build_deck(layers), on_select="rerun", selection_mode="single-object", key=map_key)
    if lounge:
        _lounge_panel(r, lounge)
    elif area_id:
        _area_panel(r, area_id)
