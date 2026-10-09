"""Area page: one growth area (populated cells beyond the drive time of every open lounge). The
GROW / WATCH / SKIP call with its rule and caveats, women, worker share, nearest lounge, the cell
map and competitor data coverage."""
import streamlit as st

from src import explain
from src.model import growth
from src.webapp import data, nav
from src.webapp.map import area_cells_layer, build_deck, flag_layer, lounge_layer, view_at
from src.webapp.views import (
    area_caveats,
    badge,
    banner,
    explanation_for,
    render_caveats,
    render_factor_table,
    render_pyramid,
    url_picker,
)

ORDER = {"GROW": 0, "WATCH": 1, "SKIP": 2}


def _check(ok: bool | None) -> str:
    return "❔" if ok is None else "✅" if ok else "❌"


def _rule(a, d) -> None:
    st.markdown("##### How this call was made")
    cols = st.columns(3)
    cols[0].metric("Women 15+", f"{a.women:,.0f}")
    cols[0].caption(f"{_check(d.big_enough)} Big enough: ≥ {growth.GROW_MIN_WOMEN:,} women and worker "
                    f"housing under {growth.WORKER_CAP:.0%} (here {a.worker_share:.0%})")
    per_1k = "no data" if a.premium_reviews_per_1k is None else f"{a.premium_reviews_per_1k:,.0f}"
    cols[1].metric("Premium reviews per 1k women", per_1k)
    cols[1].caption(f"{_check(d.unsaturated)} Unsaturated: under {growth.UNSATURATED_PER_1K:g}")
    cols[2].metric("Competitor data coverage", f"{a.data_coverage:.0%}")
    cols[2].caption(f"{_check(a.data_coverage >= growth.MIN_COVERAGE)} GROW needs ≥ "
                    f"{growth.MIN_COVERAGE:.0%} of the women in searched cells")
    st.info(f"**GROW** needs both tests (and enough searched), **WATCH** one (or big but mostly worker housing, "
            f"{growth.WORKER_CAP:.0%}+ of adults, even when saturated), **SKIP** neither; under "
            f"{growth.SKIP_UNDER_WOMEN:,} women is always SKIP. {d.rationale}")


def render() -> None:
    r = data.current()
    act = {d.area_id: d.action for d in r.area_decisions}
    by_id = {a.area_id: a for a in r.areas}
    options = sorted(by_id, key=lambda i: (ORDER[act[i]], -by_id[i].women))
    wanted = st.query_params.get("area")
    area_id = url_picker("Growth area", "area", options,
                         lambda i: f"{by_id[i].name}, {by_id[i].emirate} · {act[i]}", "area-pick")
    st.page_link(nav.OVERVIEW, label="Back to overview", icon="⬅️", query_params={"area": area_id})
    banner()
    if wanted and wanted not in by_id:
        st.info(f"{wanted} is not a growth area in this view (a lounge reaches it); showing {area_id}.")

    a = by_id[area_id]
    d = next(d for d in r.area_decisions if d.area_id == area_id)
    exp, facts = explanation_for(r, "area", area_id)
    st.header(f"Area: {a.name}, {a.emirate}")
    badge(d.action)
    left, right = st.columns([3, 2])
    with left:
        render_pyramid(exp)
    with right:
        render_caveats("Caveats for this area", area_caveats(a, d), d.action != "SKIP")
    _rule(a, d)

    layers = [area_cells_layer(data.v3().cells, r.areas, r.area_decisions, only=area_id),
              lounge_layer(r.features, r.decisions), flag_layer(r.features)]
    st.pydeck_chart(build_deck(layers, view_at(a.lat, a.lng, 9.5)), key=f"area-map-{area_id}")
    st.caption(f"Its {a.cells} grid cells (~2 km) and every lounge. The nearest is "
               f"{a.nearest_lounge_id}, {a.nearest_lounge_km:.1f} km away in a straight line.")
    st.page_link(nav.LOUNGE, label=f"Nearest lounge: {a.nearest_lounge_id} →", icon="💇",
                 query_params={"lounge": a.nearest_lounge_id})
    render_factor_table(exp, explain.AREA_TABLE, facts)
