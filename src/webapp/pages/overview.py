"""Executive Summary: the portfolio team's question answered as a pyramid: one governing thought, three key lines
(review, protect, grow), each line's evidence, and how sure we are."""
from collections import Counter

import pandas as pd
import pydeck as pdk
import streamlit as st

from src.features.lounges import site_reference
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
    short,
    source_note,
)

WEIGHTS = {s.name: s.weight for s in scorecard.SIGNALS}
QUESTION = "Where is my network under pressure, and where should we grow?"


def _n(k: int, one: str, many: str | None = None) -> str:
    return f"{k} {one if k == 1 else many or one + 's'}"


SURE = {"high": 0, "medium": 1, "low": 2}   # sort order: the calls we're surest of first


def pyramid(r) -> dict:
    """The page's argument: one governing thought and three key lines (review, protect, grow), each
    with the lounges or areas that are its evidence. Built from the run, so it can't drift from the calls.
    Each list is sorted surest first, then strongest; the thought, claims and cards count only the
    high-confidence calls ("sure")."""
    calls = {d.branch_id: d for d in r.decisions}
    act = {d.area_id: d for d in r.area_decisions}
    grow = sorted((a for a in r.areas if act[a.area_id].action == "GROW"),
                  key=lambda a: (SURE[act[a.area_id].confidence], -(a.new_site_net or 0)))
    lounges = lambda k, sign: sorted((f for f in r.features if calls[f.branch_id].action == k),
                                     key=lambda f: (SURE[calls[f.branch_id].confidence], sign * calls[f.branch_id].composite))
    protect, shrink = lounges("PROTECT", -1), lounges("SHRINK", 1)
    sure = {"grow": [a for a in grow if act[a.area_id].confidence == "high"],
            "protect": [f for f in protect if calls[f.branch_id].confidence == "high"],
            "shrink": [f for f in shrink if calls[f.branch_id].confidence == "high"]}
    lead = [e for e, _ in Counter(a.emirate for a in sure["grow"]).most_common(2)]
    thought = (f"Review {_n(len(sure['shrink']), 'weak lounge site')}, defend {_n(len(sure['protect']), 'strong one')} "
               f"and test {_n(len(sure['grow']), 'area')} for new lounges"
               + (f", most of them in {' and '.join(lead)}." if lead else "."))
    base = served_market(r)
    return {"thought": thought, "grow": grow, "protect": protect, "shrink": shrink, "sure": sure, "base": base,
            "claims": {"review": f"{_n(len(sure['shrink']), 'lounge site is', 'lounge sites are')} weak for "
                                 f"{'its' if len(sure['shrink']) == 1 else 'their'} emirate on demand or rent "
                                 f"(high confidence): review {'it' if len(sure['shrink']) == 1 else 'them'}",
                       "protect": f"{_n(len(sure['protect']), 'lounge site is', 'lounge sites are')} strong for "
                                  "their emirate (high confidence): defend them",
                       "grow": f"{_n(len(sure['grow']), 'area')} (high confidence) would each grow our served "
                               f"market by {growth.NEW_SITE_MIN / base:.0%} or more"}}


def _governing(r, p: dict) -> None:
    scored = [d for d in r.decisions if d.action != "NOT SCORED"]
    low = sum(d.confidence == "low" for d in scored)
    with st.container(border=True):
        st.markdown(f"### {p['thought']}")
        st.markdown(f"⚠️ {low} of {len(scored)} lounge calls are low confidence, and the model has no revenue or "
                    "lease data. "
                    "The headline counts high-confidence calls only. [How sure we are ↓](#how-sure-we-are)")
    with st.expander("How we measure: serviceable market per AED of commercial rent, within each emirate"):
        st.markdown(measures_text(r))
    with st.expander("Read the AI-written summary", expanded=True):
        exp = explanation_for(r, "uae", "uae")[0]    # the page in one paragraph: answer, then review, protect, grow, how sure
        st.markdown(" ".join([exp.headline] + [reason.claim for reason in exp.reasons]))
        st.caption(source_note(exp))


def served_market(r) -> float:
    """Women our open lounges serve today: the model's estimate (Huff split), the base for every % below."""
    return sum(f.served_women or 0 for f in r.features)


def measures_text(r) -> str:
    base = served_market(r)
    ours = pd.Series([f.site_rent_m2 for f in r.features if f.site_rent_m2]).quantile([0, .25, .5, .75, 1]).tolist()
    ref = site_reference()
    theirs = ref.shop_rent_m2.quantile([.25, .5, .75]).tolist()
    return (
        "Every call asks one question: **how much serviceable market does a site give us for its commercial "
        "rent, compared with other salon sites in the same emirate?** We have no bookings, revenue or lease "
        "data, so two proxies stand in:\n\n"
        "- **Demand → serviceable market.** The model estimates how many women 15+ a typical lounge at the "
        "site would serve once competing premium salons and our other lounges take their share (a Huff split "
        "over 10-20 min drives), and ranks it against its emirate's premium salon sites.\n"
        "- **Cost to run → commercial rent.** The site's shop rent against the median at its emirate's salon "
        "sites (Dubai: DLD contracts; Abu Dhabi: ADREC rates; north: listings). *Assumption:* rent is the "
        "biggest swing factor in what a branch costs. Shop rent per m² a year at our lounge sites runs AED "
        f"{ours[0]:,.0f} to {ours[-1]:,.0f} (quartiles {ours[1]:,.0f} / {ours[2]:,.0f} / {ours[3]:,.0f}); at "
        f"the {len(ref):,} salon sites the quartiles are {theirs[0]:,.0f} / {theirs[1]:,.0f} / {theirs[2]:,.0f}. "
        "Staff, products and fit-out per appointment differ far less between branches, so rent is what makes "
        "one site dearer than another.\n\n"
        "Each is scored 0-1 and the two are averaged. Emirates are compared with themselves because rents, "
        "prices and competition differ between them.\n\n"
        "**Why these thresholds.** They are judgement calls, not fitted to data (we have none to fit them to), "
        "so each has a plain reason and the calls near them are flagged:\n\n"
        f"- **PROTECT at {scorecard.PROTECT_AT}+, SHRINK at {scorecard.SHRINK_AT} or less**: "
        f"{scorecard.PROTECT_AT - 0.5:.2f} either side of a neutral 0.5. With two equal signals, even a perfect "
        "score on one needs at least 0.3 on the other to reach PROTECT (and a zero on one needs 0.7 on the other "
        "to escape SHRINK): the two have to broadly agree. The "
        "middle band (HOLD) is wide on purpose: with no revenue or lease data, a strong call needs both signals "
        f"behind it. A call within {scorecard.LOW_MARGIN} of a line is marked low confidence.\n"
        "- **Site demand score = the percentile itself**: out-serving 66% of the emirate's salon sites scores "
        "0.66, so there is no extra cut-off to argue about.\n"
        "- **Site rent score**: the rent ratio (its emirate's median salon-site rent ÷ the site's) on a 0-1 scale. "
        f"Rent {1 / scorecard.RENT_RATIO_P10:.1f}x the emirate median or more (the dearest 10% of the 1,123 salon "
        f"sites) scores 0; {1 / scorecard.RENT_RATIO_P90:.0%} of the median or less (the cheapest 10%) scores 1; "
        "in between it scales evenly, so a site at its emirate's median rent scores "
        f"{(1 - scorecard.RENT_RATIO_P10) / (scorecard.RENT_RATIO_P90 - scorecard.RENT_RATIO_P10):.2f}.\n"
        f"- **GROW needs {growth.NEW_SITE_MIN:,}+ net new women**: about what our median lounge serves today. "
        "This is our model's figure: the women 15+ it attributes to a lounge once the premium salons we count "
        "as alternatives (the competitors in the Huff split) take their share. A new lounge has to bring at least a typical lounge's worth of new customers, "
        "net of what it takes from our own lounges.\n"
        f"- **GROW needs demand in the top {1 - growth.DEMAND_PCT_MIN:.0%} and rent ratio 1x or more**: a "
        "typical lounge there would serve at least what one would at the median competitor salon site, at a "
        "rent no dearer than theirs. Both lines sit at the emirate's median salon site: \"at least as good as "
        "where our competitors already chose to be\".\n"
        "- **Low confidence** also covers calls that change in a third or more of the assumption combinations "
        "(drive time, competitor coverage, worker housing) or when a signal's weight moves ±25%.\n\n"
        f"**Growth is shown as % growth in our served market**: what a new lounge would add, net of what it "
        f"takes from our lounges, ÷ the ~{base / 1000:,.0f}k women our lounges serve today. That base is the "
        "Huff model's estimate, and it contradicts Bedashing's website, which says about 200k women across our "
        "24 lounges. That's fine for these calls: every % compares sites against the same model base, so "
        "they stay comparable even if the absolute count is low. Every count of women is the model's estimate, not a customer count.")


def _cards(p: dict) -> None:
    share = lambda fs: f"{sum(f.served_women or 0 for f in fs) / p['base']:.0%}"
    sure = p["sure"]
    top = sure["grow"][0] if sure["grow"] else None
    cards = [("1 · Review", p["claims"]["review"], share(sure["shrink"]),
              "of our served market (model estimate)", ", ".join(short(f.name, f.branch_id) for f in sure["shrink"]), "review"),
             ("2 · Protect", p["claims"]["protect"], share(sure["protect"]),
              "of our served market (model estimate)", ", ".join(short(f.name, f.branch_id) for f in sure["protect"]), "protect"),
             ("3 · Grow", p["claims"]["grow"],
              f"+{top.new_site_net / p['base']:.0%}" if top else "none",
              f"best: {top.name} (model est.)" if top else "",
              ", ".join(a.name for a in sure["grow"][:3]) + (" …" if len(sure["grow"]) > 3 else ""), "grow")]
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
                        "Vs typical lounge here": f.performance_vs_site, "Confidence": calls[f.branch_id].confidence,
}
                       for f in fs])
    right.dataframe(df, hide_index=True, column_config=_EVIDENCE_COLUMNS)
    st.caption(lounge_key(anchor) + " " + SORT_NOTE)


def _pct(x: float | None) -> int | None:
    return None if x is None else round(100 * x)


def _ratio(x: float | None) -> str:
    return "median only" if x is None else f"{x:.2f}x"


_EVIDENCE_COLUMNS = {   # no hover help: the key under each table says what each column means
    "Composite": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f"),
    "Out-serves": st.column_config.NumberColumn(format="%d%%"),
    "Rent ratio": st.column_config.TextColumn(),
    "Vs typical lounge here": st.column_config.NumberColumn(format="%.1fx"),
    "Share of market": st.column_config.NumberColumn(format="%d%%"),
    "Est. growth": st.column_config.NumberColumn(format="+%d%%"),
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
    st.caption(f"Blue cells: GROW areas; pins: our lounges. **Est. growth**: net new women a typical lounge here "
               f"would add ÷ the ~{p['base'] / 1000:,.0f}k our lounges serve today (model estimates; neighbouring "
               "areas reach the same women, so don't add them up). **Out-serves**: share of its emirate's salon "
               "sites a typical lounge here would beat on demand. **Rent ratio**: emirate median salon-site rent ÷ "
               f"this site's (above 1x = cheaper; 'median only' = no observed rent, scored neutral). **GROW** = {growth.NEW_SITE_MIN:,}+ net new women, out-serves "
               f"{growth.DEMAND_PCT_MIN:.0%}+ and rent ratio 1x+; high confidence = {growth.FAR_LINE:.0%}+ clear of the women line, "
               "with an observed rent and most of its women searched for competitors. "
               + SORT_NOTE)


def lounge_key(anchor: str) -> str:
    """The short column and decision key under a lounge evidence table."""
    rule = (f"**PROTECT** = composite {scorecard.PROTECT_AT}+" if anchor == "protect"
            else f"**SHRINK** = composite {scorecard.SHRINK_AT} or less")
    return ("**Composite**: average of the site demand and site rent scores, 0-1. **Share of market**: share of the "
            "women our lounges serve. **Out-serves**: share of its emirate's salon sites a typical lounge here "
            "would beat on demand. **Rent ratio**: emirate median salon-site rent ÷ this site's (above 1x = "
            "cheaper; 'median only' = no observed rent, scored neutral). **Vs typical lounge here**: women it serves ÷ women a typical lounge at the same site "
            f"would serve (context, not scored). {rule}; high confidence = {scorecard.HIGH_MARGIN}+ clear of "
            "both lines and stable across the assumption combinations.")


SORT_NOTE = "Sorted surest first (high, medium, low confidence), then strongest; the headline counts high only."


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
| **Site demand** (share of its emirate's salon sites it out-serves) | Is the location strong for its emirate? | A Huff split of women 15+ across premium salons, weighted by services sold (lifetime Google reviews, our proxy); distance decay and the outside option are uncalibrated | Bookings or visits per lounge (even a ranking) to calibrate the split; customers' home areas to check the catchments |
| **Site rent** (rent ratio vs the emirate's salon sites) | Is the site dear for its emirate? | Area shop rents (DLD contracts, ADREC district rates, asking rents); the emirate median where none is observed | Each lounge's actual lease; observed rents where we use the median ({lounges}, {areas}) |
| **Share of our served market** | How much of our business sits at this lounge? | The same Huff estimate, counted in women, not customers | Customers or revenue per lounge |
| **Performance vs its site** | Is the lounge beating or trailing its location? | Whether it sells more or less than a typical lounge would at its site, measured by lifetime Google reviews (our proxy for services sold) | Bookings, revenue and chair utilisation per lounge |
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
    _lounge_evidence(r, p["protect"], p["claims"]["protect"], "protect")
    st.divider()
    _grow_evidence(r, p)
    st.divider()
    _how_sure(r)
