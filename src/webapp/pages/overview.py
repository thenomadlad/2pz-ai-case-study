"""Overview: the COO's question, the executive summary and what's at stake, the limitations that matter most, the what-if panel, the map
and a short pyramid for whatever you click."""
import re
from collections import Counter

import pandas as pd
import pydeck as pdk
import streamlit as st

from src.features.lounges import substitutes
from src.model import growth, scorecard
from src.webapp import data, nav
from src.webapp.map import (
    affluence_layer,
    area_cells_layer,
    build_deck,
    catchment_cells_layer,
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
    performance_line,
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
    as a pin."""
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
    return layers + [lounge_layer(r.features, r.decisions)]


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
                    "lounge's review share is measured against.")
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
    st.markdown(f"**Growth areas** (cells beyond a {data.minutes(r.levels)}-min drive of every lounge)")
    st.markdown(f"🔵 **GROW**: a typical new lounge here would add ≥ {growth.NEW_SITE_MIN:,} net new women, "
                f"worker housing under {growth.WORKER_CAP:.0%}, out-serving {growth.DEMAND_PCT_MIN:.0%}+ of its emirate's "
                "salon sites *and* rent no dearer than their median (or unknown)  \n"
                "🟣 **WATCH**: big but dearer or weaker demand, big but mostly worker housing, or "
                f"{growth.NEW_SITE_MIN // 2:,}+ net new women  \n"
                f"⚪ **SKIP**: otherwise, under {growth.SKIP_UNDER_WOMEN:,} women, or a non-residential name")

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
        st.markdown(f"**The tests:** {_check(d.big_enough)} big enough ({a.new_site_net or 0:,.0f} net new "
                    f"women, line {growth.NEW_SITE_MIN:,}) · "
                    f"{_check(a.demand_pct is None or a.demand_pct >= growth.DEMAND_PCT_MIN)} "
                    f"{growth.demand_text(a.demand_ref, a.demand_pct, a.demand_pct_uae, a.emirate)} · "
                    f"{_check(growth.rent_ok(a))} "
                    f"{growth.rent_text(a.rent_ratio, a.rent_pct_uae, a.emirate, growth.rent_fallback(a))} · {_check(a.data_coverage >= growth.MIN_COVERAGE)} searched ({a.data_coverage:.0%} of women)")
    with right:
        render_caveats(f"Confidence: {d.confidence}. Caveats for this area", area_caveats(a, d),
                       d.action != "SKIP")
    st.page_link(nav.AREA, label="Open the area page →", icon="📍", query_params={"area": area_id})


WEIGHTS = {s.name: s.weight for s in scorecard.SIGNALS}
QUESTION = "Where is my network under pressure, and where should we grow?"


def short(name: str) -> str:
    """'Bedashing Beauty Lounge - Al Dhafra' -> 'Al Dhafra'."""
    return re.sub(r"^Bedashing Beauty Lounge\s*[-–]?\s*", "", name) or name


def _n(k: int, one: str, many: str | None = None) -> str:
    return f"{k} {one if k == 1 else many or one + 's'}"


def pyramid(r) -> dict:
    """The page's argument: one governing thought and three key lines (review, grow, protect), each
    with the lounges or areas that are its evidence. Built from the run, so it can't drift from the calls."""
    calls = {d.branch_id: d for d in r.decisions}
    lounges = {k: [f for f in r.features if calls[f.branch_id].action == k] for k in ("SHRINK", "PROTECT")}
    act = {d.area_id: d.action for d in r.area_decisions}
    grow = sorted((a for a in r.areas if act[a.area_id] == "GROW"), key=lambda a: -(a.new_site_net or 0))
    lead = [e for e, _ in Counter(a.emirate for a in grow).most_common(2)]
    shrink, protect = lounges["SHRINK"], lounges["PROTECT"]
    thought = (f"Review {_n(len(shrink), 'weak lounge site')}, defend {_n(len(protect), 'strong one')} and test "
               f"{_n(len(grow), 'area')} for new lounges" + (f", most of them in {' and '.join(lead)}." if lead else "."))
    base = served_market(r)
    return {"thought": thought, "shrink": shrink, "protect": protect, "grow": grow, "base": base,
            "claims": {"review": f"{_n(len(shrink), 'lounge site is', 'lounge sites are')} weak for "
                                 "their emirate on demand or rent: review them",
                       "grow": f"{_n(len(grow), 'area')} would each grow our served market by "
                               f"{growth.NEW_SITE_MIN / base:.0%} or more",
                       "protect": f"{_n(len(protect), 'lounge site is', 'lounge sites are')} strong for "
                                  "their emirate: defend them"}}


def _governing(r, p: dict) -> None:
    scored = [d for d in r.decisions if d.action != "NOT SCORED"]
    low = sum(d.confidence == "low" for d in scored)
    with st.container(border=True):
        st.markdown(f"### {p['thought']}")
        st.markdown(f"⚠️ {low} of {len(scored)} lounge calls are low confidence, and the model has no revenue or "
                    "lease data. [How sure we are ↓](#how-sure-we-are)")
    with st.expander("How we measure: serviceable market per AED of commercial rent, within each emirate"):
        st.markdown(measures_text(r))
    with st.expander("Read the AI-written summary"):
        render_pyramid(explanation_for(r, "uae", "uae")[0])


def served_market(r) -> float:
    """Women our open lounges serve today: the model's estimate (Huff split), the base for every % below."""
    return sum(f.served_women or 0 for f in r.features)


def measures_text(r) -> str:
    base = served_market(r)
    return (
        "Every call asks one question: **how much serviceable market does a site give us for its commercial "
        "rent, compared with other salon sites in the same emirate?** We have no bookings, revenue or lease "
        "data, so two proxies stand in:\n\n"
        "- **Demand → serviceable market.** The model estimates how many women 15+ a typical lounge at the "
        "site would serve once competing premium salons and our other lounges take their share (a Huff split "
        "over 10-20 min drives), and ranks it against its emirate's premium salon sites.\n"
        "- **Cost to run → commercial rent.** The site's shop rent against the median at its emirate's salon "
        "sites (Dubai: DLD contracts; Abu Dhabi: ADREC rates; north: listings).\n\n"
        f"Each is scored 0-1 and the two are averaged: PROTECT at {scorecard.PROTECT_AT}+, SHRINK at "
        f"{scorecard.SHRINK_AT} or less. Emirates are compared with themselves because rents, prices and "
        "competition differ between them.\n\n"
        f"**Growth is shown as % growth in our served market**: what a new lounge would add, net of what it "
        f"takes from our lounges, ÷ the ~{base / 1000:,.0f}k women our lounges serve today. Every count of "
        "women is the model's estimate, not a customer count.")


def _cards(p: dict) -> None:
    share = lambda fs: f"{sum(f.served_women or 0 for f in fs) / p['base']:.0%}"
    top = p["grow"][0] if p["grow"] else None
    cards = [("1 · Review", p["claims"]["review"], share(p["shrink"]),
              "of our served market (model estimate)", ", ".join(short(f.name) for f in p["shrink"]), "review"),
             ("2 · Grow", p["claims"]["grow"],
              f"+{top.new_site_net / p['base']:.0%}" if top else "none",
              f"best: {top.name} (model est.)" if top else "",
              ", ".join(a.name for a in p["grow"][:3]) + (" …" if len(p["grow"]) > 3 else ""), "grow"),
             ("3 · Protect", p["claims"]["protect"], share(p["protect"]),
              "of our served market (model estimate)", ", ".join(short(f.name) for f in p["protect"]), "protect")]
    for col, (label, claim, kpi, kpi_note, names, anchor) in zip(st.columns(3), cards):
        with col.container(border=True, height="stretch"):
            st.caption(label)
            st.markdown(f"**{claim[0].upper() + claim[1:]}.**")
            st.metric(kpi_note, kpi, label_visibility="visible")
            st.caption(names)
            st.markdown(f"[Evidence ↓](#{anchor})")


def _fit(points: list[tuple[float, float]], max_zoom: float = 11) -> pdk.ViewState:
    """A view that frames these (lat, lng) points, never closer than max_zoom."""
    if not points:
        return None
    view = pdk.data_utils.compute_view([[lng, lat] for lat, lng in points], view_proportion=1)
    view.zoom = min(max_zoom, view.zoom - 0.8)
    return view


def _lounge_evidence(r, fs: list, claim: str, anchor: str) -> None:
    st.subheader(claim[0].upper() + claim[1:], anchor=anchor)
    if not fs:
        st.caption("None in this run.")
        return
    calls = {d.branch_id: d for d in r.decisions}
    ids = {f.branch_id for f in fs}
    left, right = st.columns([5, 8])
    left.pydeck_chart(build_deck([lounge_layer(r.features, r.decisions, only=ids)],
                                 _fit([(f.lat, f.lng) for f in fs])), height=340)
    df = pd.DataFrame([{"Lounge": short(f.name), "Composite": calls[f.branch_id].composite,
                        "Share of market": _pct((f.served_women or 0) / served_market(r)),
                        "Out-serves": _pct(f.demand_pct), "Rent ratio": _ratio(f.rent_ratio),
                        "Vs its site": f.performance_vs_site, "Confidence": calls[f.branch_id].confidence,
                        "Page": f"/lounge?lounge={f.branch_id}"}
                       for f in sorted(fs, key=lambda f: calls[f.branch_id].composite)])
    right.dataframe(df, hide_index=True, column_config=_EVIDENCE_COLUMNS)


def _pct(x: float | None) -> int | None:
    return None if x is None else round(100 * x)


def _ratio(x: float | None) -> str:
    return "median only" if x is None else f"{x:.2f}x"


_EVIDENCE_COLUMNS = {
    "Composite": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f"),
    "Out-serves": st.column_config.NumberColumn(format="%d%%", help="Share of its emirate's competitor salon "
                                                "sites a typical lounge here would out-serve (UAE-wide where the "
                                                "emirate has under 50)"),
    "Rent ratio": st.column_config.TextColumn(help="Its emirate's median salon-site rent ÷ this site's: above "
                                              "1x = cheaper. 'median only' = only the emirate median rent is "
                                              "known, so rent is scored neutral"),
    "Vs its site": st.column_config.NumberColumn(format="%.1fx", help="Women the lounge serves ÷ women a typical "
                                                 "lounge would serve at its site: context, not scored"),
    "Share of market": st.column_config.NumberColumn(format="%d%%", help="Share of the women our lounges serve "
                                                     "today that this lounge serves (model estimate)"),
    "Est. growth": st.column_config.NumberColumn(format="+%d%%", help="Net new women a typical lounge here "
                                                 "would add ÷ the women our lounges serve today (both model "
                                                 "estimates). Not additive: neighbouring areas reach the same women"),
    "Page": st.column_config.LinkColumn(display_text="Open →")}


def _grow_evidence(r, p: dict) -> None:
    st.subheader(p["claims"]["grow"][0].upper() + p["claims"]["grow"][1:], anchor="grow")
    act = {d.area_id: d for d in r.area_decisions}
    cells = data.v3().cells
    pts = [(cells.at[c, "lat"], cells.at[c, "lng"]) for a in p["grow"] for c in a.cell_ids]
    left, right = st.columns([5, 8])
    left.pydeck_chart(build_deck([area_cells_layer(cells, p["grow"], r.area_decisions),
                                  lounge_layer(r.features, r.decisions)], _fit(pts, 9)), height=340)
    df = pd.DataFrame([{"Area": f"{a.name}, {a.emirate}", "Est. growth": _pct((a.new_site_net or 0) / p["base"]),
                        "Out-serves": _pct(a.demand_pct),
                        "Rent ratio": _ratio(None if growth.rent_fallback(a) else a.rent_ratio),
                        "Confidence": act[a.area_id].confidence, "Page": f"/area?area={a.area_id}"}
                       for a in p["grow"]])
    right.dataframe(df, hide_index=True, column_config=_EVIDENCE_COLUMNS, height=340)
    st.caption(f"Blue cells: GROW areas; pins: our lounges. Est. growth = net new women a typical lounge would "
               f"add ÷ the ~{p['base'] / 1000:,.0f}k our lounges serve today, both model estimates. The growths "
               "can't be added up: neighbouring areas reach the same women.")


def _how_sure(r) -> None:
    st.subheader("How sure we are", anchor="how-sure-we-are")
    calls = [d for d in r.decisions if d.action != "NOT SCORED"]
    hold = [d for d in calls if d.action == "HOLD"]
    near = [d for d in calls if min(abs(d.composite - scorecard.PROTECT_AT),
                                    abs(d.composite - scorecard.SHRINK_AT)) <= scorecard.LOW_MARGIN]
    low = [d for d in calls if d.confidence == "low"]
    names = {f.branch_id: short(f.name) for f in r.features}
    st.markdown(f"- **{_n(len(hold), 'lounge')} sit between the lines (HOLD):** no action, but "
                f"{_n(len(near), 'call')} overall {'is' if len(near) == 1 else 'are'} within "
                f"{scorecard.LOW_MARGIN} of a line.\n"
                f"- **{len(low)} of {len(calls)} calls are low confidence:** "
                f"{', '.join(names[d.branch_id] for d in low)}.")
    limitations_box(r)


def _lounge_table(r) -> None:
    df = pd.DataFrame([{"Lounge": f.branch_id, "Call": d.action, "Emirate": f.emirate,
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
                       for f, d in zip(r.features, r.decisions)]).sort_values("Composite", ascending=False)
    c1, c2 = st.columns(2)
    calls = c1.multiselect("Call", list(dict.fromkeys(df.Call)), key="cmp-call", placeholder="All calls")
    emirates = c2.multiselect("Emirate", sorted(df.Emirate.unique()), key="cmp-emirate", placeholder="All emirates")
    df = df[df.Call.isin(calls or df.Call) & df.Emirate.isin(emirates or df.Emirate)]
    score = st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f")
    pct = st.column_config.NumberColumn(format="percent")
    st.dataframe(df, hide_index=True, column_config={
        "Composite": score, **{n.capitalize(): score for n in WEIGHTS}, "Shared catchment": pct,
        "Demand pct (emirate)": pct, "Demand pct (UAE)": pct, "Rent pct (UAE)": pct,
        "Rent ratio": st.column_config.NumberColumn(format="%.2f"),
        "Performance vs site": st.column_config.NumberColumn(format="%.1fx"),
        "Review share": pct, "Premium reviews per 1k women": st.column_config.NumberColumn(format="%.0f"),
        "Shop rent (AED/m²/yr)": st.column_config.NumberColumn(format="%.0f"),
        "Women per AED 1k rent": st.column_config.NumberColumn(format="%.0f")})
    st.caption("Click a column header to sort. Signal scores are 0-1 on fixed scales (1 = good for the "
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


def _area_table(r) -> None:
    by_id = {a.area_id: a for a in r.areas}
    ranked = sorted((d for d in r.area_decisions if d.action != "SKIP"),
                    key=lambda d: (ORDER[d.action], -(by_id[d.area_id].new_site_net or 0)))
    df = pd.DataFrame([{"Rank": i, "Area": a.name, "Emirate": a.emirate, "Call": d.action,
                        "Net new women": round(a.new_site_net or 0), "Demand pct (emirate)": a.demand_pct,
                        "Demand pct (UAE)": a.demand_pct_uae, "Rent ratio": a.rent_ratio, "Rent pct (UAE)": a.rent_pct_uae,
                        "Women 15+": round(a.women), "Worker housing": a.worker_share,
                        "Premium reviews per 1k women": a.premium_reviews_per_1k, "Searched": a.data_coverage,
                        "Shop rent (AED/m²/yr)": a.shop_rent_m2, "Women per AED 1k rent": a.women_per_rent_k,
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
        "Worker housing": pct, "Searched": pct, "Demand pct (emirate)": pct, "Demand pct (UAE)": pct,
        "Rent pct (UAE)": pct, "Rent ratio": st.column_config.NumberColumn(format="%.2f"),
        "Premium reviews per 1k women": st.column_config.NumberColumn(format="%.0f"),
        "Shop rent (AED/m²/yr)": st.column_config.NumberColumn(format="%.0f"),
        "Women per AED 1k rent": st.column_config.NumberColumn(format="%.0f"),
        "Why": st.column_config.TextColumn(width="large")})
    st.caption("Ranked GROW first, then WATCH, each by net new women (what a typical new lounge would add to the "
               "network, net of what it takes from our lounges). Demand pct: share of its emirate's salon sites a new lounge here would out-serve (GROW needs "
               f"{growth.DEMAND_PCT_MIN:.0%}; UAE-wide where the emirate has under 50); rent ratio: their median shop rent ÷ the "
               "area's (GROW needs 1+); UAE columns: the same against all UAE salon sites. Why: the tests it passed or "
               "failed. SKIP areas are left out. Shop rent is our cost; women per AED 1k assumes a 150 m² "
               "unit (and counts the whole area's women against one unit's rent).")


def render() -> None:
    st.title("Bedashing UAE network")
    banner()
    r = data.current()
    st.markdown(f"#### {QUESTION}")
    p = pyramid(r)
    _governing(r, p)
    _cards(p)
    st.divider()
    _lounge_evidence(r, p["shrink"], p["claims"]["review"], "review")
    st.divider()
    _grow_evidence(r, p)
    st.divider()
    _lounge_evidence(r, p["protect"], p["claims"]["protect"], "protect")
    st.divider()
    _how_sure(r)

    st.divider()
    st.subheader("Explore")
    render_panel()
    st.markdown("##### The map: click a lounge or an area")
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

    st.markdown("##### Compare everything")
    lounges, areas = st.tabs(["Lounges", "Growth areas, ranked"])
    with lounges:
        _lounge_table(r)
    with areas:
        _area_table(r)
