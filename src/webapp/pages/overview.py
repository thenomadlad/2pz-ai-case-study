"""Executive Summary: the COO's question answered as a pyramid: one governing thought, three key lines
(review, grow, protect), each line's evidence, and how sure we are."""
from collections import Counter

import pandas as pd
import pydeck as pdk
import streamlit as st

from src.model import growth, scorecard
from src.webapp import data
from src.webapp.map import (
    area_cells_layer,
    build_deck,
    lounge_layer,
)
from src.webapp.views import (
    explanation_for,
    limitations_box,
    render_pyramid,
    short,
)

WEIGHTS = {s.name: s.weight for s in scorecard.SIGNALS}
QUESTION = "Where is my network under pressure, and where should we grow?"


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
        "sites (Dubai: DLD contracts; Abu Dhabi: ADREC rates; north: listings). *Assumption:* rent is the "
        "biggest swing factor in what a branch costs. It differs about 10x across our sites (roughly AED 480 "
        "to 4,560 per m² a year), while staff, products and fit-out per appointment differ far less between "
        "branches, so rent is what makes one site dearer than another.\n\n"
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
              "of our served market (model estimate)", ", ".join(short(f.name, f.branch_id) for f in p["shrink"]), "review"),
             ("2 · Grow", p["claims"]["grow"],
              f"+{top.new_site_net / p['base']:.0%}" if top else "none",
              f"best: {top.name} (model est.)" if top else "",
              ", ".join(a.name for a in p["grow"][:3]) + (" …" if len(p["grow"]) > 3 else ""), "grow"),
             ("3 · Protect", p["claims"]["protect"], share(p["protect"]),
              "of our served market (model estimate)", ", ".join(short(f.name, f.branch_id) for f in p["protect"]), "protect")]
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
    df = pd.DataFrame([{"Lounge": f"/lounge?lounge={f.branch_id}&name={short(f.name, f.branch_id)}", "Composite": calls[f.branch_id].composite,
                        "Share of market": _pct((f.served_women or 0) / served_market(r)),
                        "Out-serves": _pct(f.demand_pct), "Rent ratio": _ratio(f.rent_ratio),
                        "Vs its site": f.performance_vs_site, "Confidence": calls[f.branch_id].confidence,
}
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
    # the name is the link (opens its page in a new tab); display_text shows the name carried in the URL
    "Lounge": st.column_config.LinkColumn(display_text=r"name=(.*)$"),
    "Area": st.column_config.LinkColumn(display_text=r"name=(.*)$")}


def _grow_evidence(r, p: dict) -> None:
    st.subheader(p["claims"]["grow"][0].upper() + p["claims"]["grow"][1:], anchor="grow")
    act = {d.area_id: d for d in r.area_decisions}
    cells = data.v3().cells
    pts = [(cells.at[c, "lat"], cells.at[c, "lng"]) for a in p["grow"] for c in a.cell_ids]
    left, right = st.columns([5, 8])
    left.pydeck_chart(build_deck([area_cells_layer(cells, p["grow"], r.area_decisions),
                                  lounge_layer(r.features, r.decisions)], _fit(pts, 9)), height=340)
    df = pd.DataFrame([{"Area": f"/area?area={a.area_id}&name={a.name}, {a.emirate}", "Est. growth": _pct((a.new_site_net or 0) / p["base"]),
                        "Out-serves": _pct(a.demand_pct),
                        "Rent ratio": _ratio(None if growth.rent_fallback(a) else a.rent_ratio),
                        "Confidence": act[a.area_id].confidence}
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
    names = {f.branch_id: short(f.name, f.branch_id) for f in r.features}
    st.markdown(f"- **{_n(len(hold), 'lounge')} sit between the lines (HOLD):** no action, but "
                f"{_n(len(near), 'call')} overall {'is' if len(near) == 1 else 'are'} within "
                f"{scorecard.LOW_MARGIN} of a line.\n"
                f"- **{len(low)} of {len(calls)} calls are low confidence:** "
                f"{', '.join(names[d.branch_id] for d in low)}.")
    with st.container(border=True):
        st.markdown("#### Branch health KPIs, and what would make us surer of them")
        act = {d.area_id: d.action for d in r.area_decisions}
        st.markdown(KPI_TABLE.format(
            lounges=_n(sum(f.site_rent_source == "emirate_median" for f in r.features), "lounge"),
            areas=_n(sum(act[a.area_id] == "GROW" and growth.rent_fallback(a) for a in r.areas), "GROW area")))
    limitations_box(r)


KPI_TABLE = """| Branch health KPI | What it tells us | Today it rests on | To be more confident we need |
|---|---|---|---|
| **Site demand** (share of its emirate's salon sites it out-serves) | Is the location strong for its emirate? | A Huff split of women 15+ across premium salons, weighted by lifetime Google reviews; distance decay and the outside option are uncalibrated | Bookings or visits per lounge (even a ranking) to calibrate the split; customers' home areas to check the catchments |
| **Site rent** (rent ratio vs the emirate's salon sites) | Is the site dear for its emirate? | Area shop rents (DLD contracts, ADREC district rates, asking rents); the emirate median where none is observed | Each lounge's actual lease; observed rents where we use the median ({lounges}, {areas}) |
| **Share of our served market** | How much of our business sits at this lounge? | The same Huff estimate, counted in women, not customers | Customers or revenue per lounge |
| **Performance vs its site** | Is the lounge beating or trailing its location? | Its lifetime Google reviews as a stand-in for popularity | Bookings, revenue and chair utilisation per lounge |
| **The call** (PROTECT / HOLD / SHRINK) | Keep, watch or review? | Demand and rent only: no revenue, margin, capex or capacity | Revenue, margin, capex and capacity per lounge, for a return-on-capital test |
"""


def render() -> None:
    st.title("Bedashing UAE network")
    r = data.baseline()
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
