"""Area page: one growth area (populated cells beyond the current travel-time catchment, 15 min at
baseline, of every open lounge). The GROW / WATCH / SKIP call (what-if: open a typical lounge here) with
its rule and caveats, net new women, demand percentile and rent ratio (salon-site reference), worker share, nearest lounge and the cell map."""
import streamlit as st

from src import explain
from src.model import growth
from src.webapp import data, nav
from src.webapp.map import area_cells_layer, build_deck, flag_layer, lounge_layer, view_at
from src.webapp.views import (
    affluence_metrics,
    area_caveats,
    badge,
    banner,
    emirate_filter,
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
    cols = st.columns(4)
    net = "no data" if a.new_site_net is None else f"{a.new_site_net:,.0f}"
    cols[0].metric("Net new women (what-if lounge)", net)
    cols[0].caption(f"{_check(d.big_enough)} Big enough: ≥ {growth.NEW_SITE_MIN:,} net new women and worker "
                    f"housing under {growth.WORKER_CAP:.0%} (here {a.worker_share:.0%})")
    cols[1].metric("Site demand percentile", "no data" if a.demand_pct is None else f"{a.demand_pct:.0%}")
    cols[1].caption(f"{_check(a.demand_pct is None or a.demand_pct >= growth.DEMAND_PCT_MIN)} At least "
                    f"{growth.DEMAND_PCT_MIN:.0%}: " + growth.demand_text(a.demand_ref, a.demand_pct, a.demand_pct_uae, a.emirate))
    cols[2].metric("Rent ratio", "no data" if a.rent_ratio is None else f"{a.rent_ratio:.2f}")
    cols[2].caption(f"{_check(a.rent_ratio is None or a.rent_ratio >= growth.RENT_RATIO_MIN)} Not dearer: "
                    + growth.rent_text(a.rent_ratio, a.rent_pct_uae, a.emirate) + "; unknown passes")
    per_1k = "no data" if a.premium_reviews_per_1k is None else f"{a.premium_reviews_per_1k:,.0f}"
    cols[3].metric("Premium reviews per 1k women", per_1k)
    cols[3].caption(f"Saturation, context only (our lightest-quarter line is {growth.UNSATURATED_PER_1K:g}); "
                    f"{a.data_coverage:.0%} of the women searched for competitors")
    st.info(f"What-if: open a typical lounge here. **GROW** needs all three checks, **WATCH** is big but dearer, weaker demand or "
            f"mostly worker housing ({growth.WORKER_CAP:.0%}+ of adults), or adds "
            f"{growth.NEW_SITE_MIN // 2:,}+ net new women; **SKIP** otherwise. Under "
            f"{growth.SKIP_UNDER_WOMEN:,} women or a non-residential name is always SKIP. {d.rationale}")

def render() -> None:
    r = data.current()
    act = {d.area_id: d.action for d in r.area_decisions}
    by_id = {a.area_id: a for a in r.areas}
    # areas under the SKIP floor are noise: always SKIP, whatever the competition, so not listed
    options = sorted((i for i in by_id if by_id[i].women >= growth.SKIP_UNDER_WOMEN),
                     key=lambda i: (ORDER[act[i]], -by_id[i].women))
    grow = frozenset(by_id[i].emirate for i in options if act[i] == "GROW")
    options = emirate_filter(options, {i: by_id[i].emirate for i in options}, "area", "area-em", also=grow)
    wanted = st.query_params.get("area")
    area_id = url_picker("Growth area", "area", options,
                         lambda i: f"{by_id[i].name}, {by_id[i].emirate} · {act[i]}", "area-pick")
    st.page_link(nav.OVERVIEW, label="Back to overview", icon="⬅️", query_params={"area": area_id})
    banner()
    if wanted and wanted not in options:
        st.info(f"That area isn't listed in this view (a lounge reaches it, it has under "
                f"{growth.SKIP_UNDER_WOMEN:,} women, or the link is wrong); "
                f"showing {area_id}.")

    a = by_id[area_id]
    d = next(d for d in r.area_decisions if d.area_id == area_id)
    exp, facts = explanation_for(r, "area", area_id)
    st.header(f"Area: {a.name}, {a.emirate}")
    badge(d.action)
    left, right = st.columns([3, 2])
    with left:
        render_pyramid(exp)
    with right:
        render_caveats(f"Confidence: {d.confidence}. Caveats for this area", area_caveats(a, d),
                       d.action != "SKIP")
    _rule(a, d)
    affluence_metrics(a.women, a.addressable_women, a.affluence_rent, a.affluence_coverage)

    layers = [area_cells_layer(data.v3().cells, r.areas, r.area_decisions, only=area_id),
              lounge_layer(r.features, r.decisions), flag_layer(r.features)]
    st.pydeck_chart(build_deck(layers, view_at(a.lat, a.lng, 9.5)), key=f"area-map-{area_id}")
    st.caption(f"Its {a.cells} grid cells (~2 km) and every lounge. The nearest is "
               f"{a.nearest_lounge_id}, {a.nearest_lounge_km:.1f} km away in a straight line.")
    st.page_link(nav.LOUNGE, label=f"Nearest lounge: {a.nearest_lounge_id} →", icon="💇",
                 query_params={"lounge": a.nearest_lounge_id})
    render_factor_table(exp, explain.AREA_TABLE, facts)
