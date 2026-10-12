"""Area page: one growth area (populated cells beyond the current travel-time catchment, 15 min at
baseline, of every open lounge). The GROW / WATCH / SKIP call (what-if: open a typical lounge here) with
its rule and caveats, net new women, demand percentile and rent ratio (salon-site reference), worker share, nearest lounge and the cell map."""
import pandas as pd
import streamlit as st

from src import explain
from src.model import growth
from src.webapp import data, nav
from src.webapp.map import area_cells_layer, build_deck, lounge_layer, view_at
from src.webapp.views import (
    area_caveats,
    badge,
    explanation_for,
    render_assumptions,
    render_caveats,
    render_factor_table,
    render_pyramid,
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
    cols[2].caption(f"{_check(growth.rent_ok(a))} Not dearer: "
                    + growth.rent_text(a.rent_ratio, a.rent_pct_uae, a.emirate, growth.rent_fallback(a))
                    + "; unknown or emirate-median fallback passes")
    per_1k = "no data" if a.premium_reviews_per_1k is None else f"{a.premium_reviews_per_1k:,.0f}"
    cols[3].metric("Premium reviews per 1k women", per_1k)
    cols[3].caption(f"Saturation, context only (our lightest-quarter line is {growth.UNSATURATED_PER_1K:g}); "
                    f"{a.data_coverage:.0%} of the women searched for competitors")
    st.info(f"What-if: open a typical lounge here. **GROW** needs all three checks, **WATCH** is big but dearer, weaker demand or "
            f"mostly worker housing ({growth.WORKER_CAP:.0%}+ of adults), or adds "
            f"{growth.NEW_SITE_MIN // 2:,}+ net new women; **SKIP** otherwise. Under "
            f"{growth.SKIP_UNDER_WOMEN:,} women or a non-residential name is always SKIP. {d.rationale}")

def _area_table(r) -> str | None:
    """The ranked table, which is also the picker: returns the selected row's area, if any."""
    by_id = {a.area_id: a for a in r.areas}
    ranked = sorted((d for d in r.area_decisions if d.action != "SKIP"),
                    key=lambda d: (ORDER[d.action], -(by_id[d.area_id].new_site_net or 0)))
    df = pd.DataFrame([{"id": a.area_id, "Rank": i, "Area": a.name, "Emirate": a.emirate, "Call": d.action,
                        "Net new women": round(a.new_site_net or 0), "Demand pct (emirate)": a.demand_pct,
                        "Demand pct (UAE)": a.demand_pct_uae, "Rent ratio": a.rent_ratio, "Rent pct (UAE)": a.rent_pct_uae,
                        "Women 15+": round(a.women), "Worker housing": a.worker_share,
                        "Premium reviews per 1k women": a.premium_reviews_per_1k, "Searched": a.data_coverage,
                        "Shop rent (AED/m²/yr)": a.shop_rent_m2, "Women per AED 1k rent": a.women_per_rent_k,
                        "Nearest lounge": a.nearest_lounge_id, "km (straight line)": round(a.nearest_lounge_km, 1),
                        "Confidence": d.confidence,
                        "Why": d.rationale.split(" Nearest lounge:")[0]}
                       for i, d in enumerate(ranked, start=1) for a in [by_id[d.area_id]]]).set_index("id")
    c1, c2 = st.columns(2)
    calls = c1.multiselect("Call", ["GROW", "WATCH"], key="cmp-area-call", placeholder="GROW and WATCH")
    emirates = c2.multiselect("Emirate", sorted(df.Emirate.unique()), key="cmp-area-emirate",
                              placeholder="All emirates")
    df = df[df.Call.isin(calls or df.Call) & df.Emirate.isin(emirates or df.Emirate)]
    pct = st.column_config.NumberColumn(format="percent")
    event = st.dataframe(df, hide_index=True, on_select="rerun", selection_mode="single-row", key="area-table",
                         column_config={
        "Worker housing": pct, "Searched": pct, "Demand pct (emirate)": pct, "Demand pct (UAE)": pct,
        "Rent pct (UAE)": pct, "Rent ratio": st.column_config.NumberColumn(format="%.2f"),
        "Premium reviews per 1k women": st.column_config.NumberColumn(format="%.0f"),
        "Shop rent (AED/m²/yr)": st.column_config.NumberColumn(format="%.0f"),
        "Women per AED 1k rent": st.column_config.NumberColumn(format="%.0f"),
        "Why": st.column_config.TextColumn(width="large")})
    st.caption("Select a row to show that area below. Ranked GROW first, then WATCH, each by net new women (what a typical new lounge would add to the "
               "network, net of what it takes from our lounges). Demand pct: share of its emirate's salon sites a new lounge here would out-serve (GROW needs "
               f"{growth.DEMAND_PCT_MIN:.0%}; UAE-wide where the emirate has under 50); rent ratio: their median shop rent ÷ the "
               "area's (GROW needs 1+); UAE columns: the same against all UAE salon sites. Why: the tests it passed or "
               "failed. SKIP areas are left out. Shop rent is our cost; women per AED 1k assumes a 150 m² "
               "unit (and counts the whole area's women against one unit's rent).")
    rows = event.selection.rows
    return df.index[rows[0]] if rows else None


def render() -> None:
    r = data.baseline()
    st.title("Areas")
    st.subheader("All growth areas, ranked")
    picked = _area_table(r)
    st.divider()
    act = {d.area_id: d.action for d in r.area_decisions}
    by_id = {a.area_id: a for a in r.areas}
    top = min(by_id, key=lambda i: (ORDER[act[i]], -(by_id[i].new_site_net or 0)))
    wanted = st.query_params.get("area")
    # a row click wins, then a link's ?area= (any area, SKIP too: the map links here), else the top GROW area.
    # Only known ids are used: the URL is untrusted
    area_id = picked or (wanted if wanted in by_id else top)
    st.query_params["area"] = area_id
    st.page_link(nav.PREDICTIONS, label="Show on the map", icon="🗺️", query_params={"area": area_id})

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
    render_factor_table(exp, explain.AREA_TABLE, facts)
    render_assumptions("area", area_id)

    layers = [area_cells_layer(data.v3().cells, r.areas, r.area_decisions, only=area_id),
              lounge_layer(r.features, r.decisions)]
    st.pydeck_chart(build_deck(layers, view_at(a.lat, a.lng, 9.5)), key=f"area-map-{area_id}")
    st.caption(f"Its {a.cells} grid cells (~2 km) and every lounge. The nearest is "
               f"{a.nearest_lounge_id}, {a.nearest_lounge_km:.1f} km away in a straight line.")
    st.page_link(nav.LOUNGE, label=f"Nearest lounge: {a.nearest_lounge_id} →", icon="💇",
                 query_params={"lounge": a.nearest_lounge_id})
