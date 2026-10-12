"""Rendering pieces shared by the pages: the what-if banner, explanations, tables, caveats and the
"before you trust these calls" box."""
import re
from functools import cache

import pandas as pd
import streamlit as st

from src import explain
from src.baseline import Run
from src.config import settings
from src.model import growth, scorecard
from src.models import Area, AreaDecision, Decision, Explanation, Levels, LoungeFeatures, Rules
from src.webapp import data

BADGE_COLORS = {"PROTECT": "green", "HOLD": "orange", "SHRINK": "red", "NOT SCORED": "gray",
                "GROW": "blue", "WATCH": "violet", "SKIP": "gray"}
FEW_REVIEWS = 300   # under this many lifetime reviews, served demand understates a lounge (noya-plaza: 215)
WORKER_NOTE = 0.25  # from this share of adults in worker housing, the women estimate leans on that assumption
SHARJAH_LOUNGES = ("al-jada", "zawaya-walk")
FULLY_SEARCHED = 0.99  # under this share of women in searched cells, say saturation covers only part of the area


# --- what-if labels and banner ------------------------------------------------------------

def level_label(axis: str, level: str) -> str:
    """"15 min (medium)", "60% of premium reviews (medium)", "5.5% women (medium)",
    "medium: rent^0.5 (medium)"."""
    a = data.assumptions()
    if axis == "travel":
        return f"{a.travel_time_minutes[level]} min ({level})"
    if axis == "coverage":
        return f"{a.competitor_coverage[level]:.0%} of premium reviews ({level})"
    return f"{a.worker_housing_female_share[level]:.1%} women ({level})"


def what_if_summary() -> str:
    w, base, parts = data.what_if(), Levels(), []
    for axis, name in (("travel", "travel time"), ("coverage", "competitor coverage"),
                       ("worker_share", "worker-housing women")):
        if getattr(w["levels"], axis) != getattr(base, axis):
            parts.append(f"{name} {level_label(axis, getattr(w['levels'], axis))}")
    if w["recall"] is not None:
        parts.append(f"search recall {w['recall']:.2f}")
    if w["closed"]:
        parts.append("closed: " + ", ".join(sorted(w["closed"])))
    parts += rules_summary(w["rules"])
    parts += [quote_label(sid, q) for sid, q in sorted(w["quotes"].items())]
    return "; ".join(parts)


def rules_summary(r: Rules) -> list[str]:
    """The decision rules that differ from the baseline's, in words."""
    base, out = Rules(), []
    if r.demand_weight != base.demand_weight:
        out.append(f"demand weight {r.demand_weight:.0%} (rent {1 - r.demand_weight:.0%})")
    if r.protect_at != base.protect_at:
        out.append(f"PROTECT line {r.protect_at:.2f}")
    if r.shrink_at != base.shrink_at:
        out.append(f"SHRINK line {r.shrink_at:.2f}")
    if r.grow_min != base.grow_min:
        out.append(f"GROW minimum {r.grow_min:,} net new women")
    if r.demand_pct_min != base.demand_pct_min:
        out.append(f"GROW demand line {r.demand_pct_min:.0%}")
    return out


def site_name(sid: str) -> str:
    """A lounge's short name or an area's name, for any site id a what-if can name."""
    lo = next((lo for lo in data.v3().lounges if lo.branch_id == sid), None)
    if lo:
        return short(lo.title, sid)
    a = next((a for get in (data.baseline, data.current) for a in get().areas if a.area_id == sid), None)
    return a.name if a else sid


def quote_label(sid: str, rent: float) -> str:
    return f"{site_name(sid)} at AED {rent:,.0f}/m² (quote)"


def banner() -> None:
    if data.active():
        st.warning(f"**What-if view**, not the baseline: {what_if_summary()}. Only this page "
                   "changes: the Executive Summary, Lounges and Areas show the baseline.", icon="🧪")


# --- explanations -------------------------------------------------------------------------

@cache
def _cache() -> dict:
    return explain.load_cache()


def get_explanation(kind: str, subject_id: str, action: str, facts: dict) -> Explanation:
    """Cached AI text when these exact numbers were explained, else the template. Never calls an API."""
    return explain.explain(kind, subject_id, action, facts, cache=_cache(), client=None)


def explanation_for(r: Run, kind: str, subject_id: str) -> tuple[Explanation, dict]:
    action, facts = data.subject(r, kind, subject_id)
    return get_explanation(kind, subject_id, action, facts), facts


def source_note(exp: Explanation) -> str:
    if exp.source == "ai":
        return "AI-written (cached): every number in it was checked against the data."
    if not explain.needs_ai(exp.action):
        return "Template (fixed rules): SKIP areas and NOT SCORED lounges always use it."
    return ("Template — numbers changed by the what-if, so the cached AI text no longer applies."
            if data.active() else "Template (fixed rules): no cached AI text for these numbers.")


def badge(action: str) -> None:
    st.badge(action, color=BADGE_COLORS.get(action, "gray"))


def render_pyramid(exp: Explanation) -> None:
    """Answer first, then each ranked argument with its data points, then where the text came from."""
    st.markdown(f"**{exp.headline}**")
    for i, reason in enumerate(exp.reasons, start=1):
        label = explain.TOPIC_LABELS.get(reason.topic, reason.topic)
        st.markdown(f"{i}. **{label}.** {reason.claim}")
        st.caption(" · ".join(f"{e.label}: {explain.fmt(e.field, e.value)}" for e in reason.evidence))
    if getattr(exp, "so_what", ""):
        st.markdown(f"**So what.** {exp.so_what}")
    if getattr(exp, "now_what", ""):
        st.markdown(f"**Now what.** {exp.now_what}")
    st.caption(source_note(exp))


def val(field: str, value) -> str:
    """A value with its unit ("105,000 women", "12%")."""
    f = explain.GLOSSARY[field]
    text = explain.fmt(field, value)
    return text if f.pct or value is None or isinstance(value, bool) else f"{text} {f.unit}"


def wrapped_table(rows: list[dict]) -> None:
    """A static table that wraps long text; the first column labels the rows."""
    df = pd.DataFrame(rows)
    st.table(df.set_index(df.columns[0]))


def _fetched(csv: str) -> str:
    """The snapshot date(s) in a seed table's fetched_at column ("2026-10-09")."""
    days = sorted(pd.read_csv(settings.v3_dir / csv, usecols=["fetched_at"]).fetched_at.str[:10].unique())
    return days[0] if len(days) == 1 else f"{days[0]} to {days[-1]}"


def rent_source(kind: str, subject_id: str, facts: dict) -> str:
    """Where this subject's shop rent comes from: a lounge's site cell source (dld | adrec | listings |
    emirate_median | none); an area's from its emirate, or the fallback when that sets its rent."""
    if kind == "lounge":
        return next((f.site_rent_source for f in data.baseline().features if f.branch_id == subject_id), "none")
    if facts.get("rent_ratio") is None:
        return "none"
    if facts.get("rent_fallback"):
        return "emirate_median"
    return {"Dubai": "dld", "Abu Dhabi": "adrec"}.get(facts.get("emirate"), "listings")


@cache
def provenance(kind: str, rent: str) -> str:
    """Where the factor table's numbers come from, with snapshot dates read from the data (S7);
    `rent` is the subject's shop-rent source (rent_source)."""
    dates = re.search(r"registered (\d{4}-\d\d-\d\d) to (\d{4}-\d\d-\d\d)",
                      (settings.v3_dir / "SOURCES.md").read_text())
    rents = {"dld": "DLD Ejari shop contracts" + (f" registered {dates[1]} to {dates[2]}" if dates else ""),
             "adrec": "ADREC 2025 street-retail district rates, read off its public map",
             "listings": "Property Finder / Bayut shop asking rents, scraped 2026-10-11",
             "emirate_median": "none observed here: the emirate's median shop rent stands in",
             "quote": "the quoted rent"}
    parts = [f"competitors: Google Places, fetched {_fetched('salons.csv')}",
             "women 15+: WorldPop 2025 (R2025A), rebalanced for OSM worker housing",
             f"drive times: Mapbox isochrones, typical traffic at {data.assumptions().isochrone_depart_at.replace('T', ' ')}"]
    if rent in rents:
        parts.append(f"shop rent: {rents[rent]}")
    if kind == "lounge":
        parts.insert(0, f"lounge rating and reviews: Google Places, fetched {_fetched('branches.csv')}")
    return "Sources: " + "; ".join(parts) + ". Details in data/seed/v3/SOURCES.md."


def render_factor_table(exp: Explanation, fields: tuple[str, ...], facts: dict) -> None:
    st.caption(exp.table_caption)
    changes = explain.what_would_change(exp.kind, facts)
    if changes:
        st.markdown("**What would change the call.** " + " ".join(changes))
    from src.webapp import factor_tree
    factor_tree.render(exp.kind, {**facts, "action": exp.action})
    st.caption(provenance(exp.kind, rent_source(exp.kind, exp.subject_id, facts)))


def limitations_box(r: Run) -> None:
    """The three caveats that matter most, right under the executive summary; docs/limitations.md holds the full list."""
    scored = [d for d in r.decisions if d.action != "NOT SCORED"]
    low = sum(d.confidence == "low" for d in scored)
    with st.container(border=True):
        st.markdown("#### ⚠️ Before you trust these calls")
        st.markdown(
            "A shortlist to test with the business, not decisions: **No revenue or lease data in the model** "
            "(SHRINK means *investigate*, not *close*), services sold are measured by lifetime Google reviews, "
            f"and **{low} of {len(scored)}** lounge calls are low confidence.  \n"
            "[All the limitations →](/limitations) · [The model we'd build with Bedashing's data →](/decision-model#the-ideal-model-the-same-decisions-on-bedashings-own-metrics)")


def performance_line(f) -> str:
    """The owner's wording for performance_vs_site, with the two numbers behind it: context, not scored."""
    if f.performance_vs_site is None:
        return "No site estimate to compare this lounge's served women with."
    return (f"**{explain.performance_sentence(f.performance_vs_site)}** ({f.served_women:,.0f} women served "
            f"vs {f.site_served:,.0f} a typical lounge would serve at its site). Context, not scored: the call "
            "scores the site, not the lounge.")


def near_threshold(d: Decision) -> str | None:
    for name, line in (("PROTECT", scorecard.PROTECT_AT), ("SHRINK", scorecard.SHRINK_AT)):
        if abs(d.composite - line) < scorecard.LOW_MARGIN:
            return (f"Composite {d.composite:.2f} is within {scorecard.LOW_MARGIN} of the {name} line ({line}): a small "
                    "change in any input moves the call.")
    return None


def lounge_caveats(f: LoungeFeatures, d: Decision, flips: int | None) -> list[str]:
    """Everything that weakens this lounge's call, most specific first."""
    if d.action == "NOT SCORED":
        return [d.rationale, ("It stays on the map but is left out of every comparison: it is no "
                              "lounge's sibling or substitute, no area's nearest lounge, and its "
                              "catchment is open to growth areas.")]
    out = [c for c in (near_threshold(d),) if c] + d.caveats[1:]
    if flips and flips < scorecard.FLIP_LOW:
        out.append(f"The call changes in {flips} of {scorecard.COMBOS} assumption combinations (low "
                   f"confidence from {scorecard.FLIP_LOW}).")
    if f.demand_ref == "UAE":
        out.append(f"{f.emirate} has under 50 reference salon sites: its demand is ranked against all UAE salon sites.")
    if f.review_count < FEW_REVIEWS:
        out.append(f"Only {f.review_count:,} lifetime Google reviews. Served demand splits each cell by "
                   "lifetime reviews, so a newer lounge's served women (and performance vs site) look weaker "
                   "than they are.")
    if f.branch_id == "mirdif-35":
        out.append("Market overstated: worker housing not mapped as industrial in OpenStreetMap "
                   "(Dubai Investment Park, very likely Sonapur) counts as ordinary housing here.")
    return out + d.caveats[:1]      # no revenue or lease data, last: it applies to every lounge


def area_caveats(a: Area, d: AreaDecision) -> list[str]:
    out = list(d.caveats)
    if a.premium_reviews_per_1k is not None and growth.MIN_COVERAGE <= a.data_coverage < FULLY_SEARCHED:
        out.append(f"Competitor data covers {a.data_coverage:.0%} of the women here; saturation is "
                   "computed over the searched cells only.")
    if a.worker_share >= WORKER_NOTE:
        out.append(f"{a.worker_share:.0%} of adults live in worker housing: the women estimate rests "
                   "on the worker-housing female share assumption.")
    if a.emirate == "Sharjah":
        reach, women = data.reached(Levels(), frozenset()), data.women(Levels().worker_share)
        near = [c for c in a.cell_ids if set(reach.get(c, ())) & set(SHARJAH_LOUNGES)]
        where = (f"they already reach {women[near].sum() / women[a.cell_ids].sum():.0%} of this area's women within "
                 f"a {data.minutes(Levels())}-min drive" if near else
                 f"this area is beyond the drive time of both ({a.nearest_lounge_id} is nearest)")
        out.append(f"Bedashing's only Sharjah lounges (al-jada, zawaya-walk) are on the Dubai side; {where}. Why the "
                   "footprint is only two lounges is a business question: the model can't see licensing, "
                   "brand fit, landlord terms or customer mix.")
    out.append(f"Distance to the nearest lounge ({a.nearest_lounge_km:.1f} km to {a.nearest_lounge_id}) "
               "is a straight line, not a drive.")
    return out


def render_caveats(title: str, items: list[str], strong: bool) -> None:
    """Caveats as a visible box: a warning when they weaken the call, else an info box."""
    (st.warning if strong else st.info)(f"**{title}**\n\n" + "\n".join(f"- {c}" for c in items))


def short(name: str, branch_id: str = "") -> str:
    """'Bedashing Beauty Lounge - Al Dhafra' -> 'Al Dhafra'."""
    rest = re.sub(r"^Bedashing Beauty Lounge\s*[-–]?\s*", "", name)
    return rest or (branch_id.replace("-", " ").title() if branch_id else name)


def render_assumptions(kind: str, sid: str) -> None:
    """How this lounge's or area's key estimates and call move as each assumption moves (others at baseline)."""
    st.markdown("##### How the estimates move with the assumptions")
    st.caption("Each tab moves one assumption and keeps the others at their baseline. All figures are the "
               "model's estimates.")
    base = Levels()
    for tab, (axis, name) in zip(st.tabs([n for _, n in data.AXES]), data.AXES):
        rows = []
        for lv in data.LEVELS:
            lounges, areas, served = data.at_level(axis, lv)
            label = level_label(axis, lv) + (" · baseline" if lv == getattr(base, axis) else "")
            if kind == "lounge":
                f, d = lounges.get(sid, (None, None))
                if f is None:
                    continue
                rows.append({"Assumption": label, "Women in catchment": round(f.catchment_women),
                             "Site demand": None if f.site_served is None else round(f.site_served),
                             "Served by this lounge": round(f.served_women or 0),
                             "Share of our market": round(100 * (f.served_women or 0) / served) if served else None,
                             "Out-serves": None if f.demand_pct is None else round(100 * f.demand_pct),
                             "Composite": None if d.action == "NOT SCORED" else d.composite, "Call": d.action})
            else:
                a, d = areas.get(sid, (None, None))
                if a is None:
                    rows.append({"Assumption": label, "Call": "not an area here"})
                    continue
                rows.append({"Assumption": label, "Women 15+": round(a.women),
                             "Net new women": round(a.new_site_net or 0),
                             "Est. growth": round(100 * (a.new_site_net or 0) / served) if served else None,
                             "Out-serves": None if a.demand_pct is None else round(100 * a.demand_pct),
                             "Call": d.action})
        tab.dataframe(pd.DataFrame(rows), hide_index=True, column_config={
            "Composite": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f"),
            "Site demand": st.column_config.NumberColumn(help="Women a typical lounge would serve at this site"),
            "Share of our market": st.column_config.NumberColumn(format="%d%%"),
            "Out-serves": st.column_config.NumberColumn(format="%d%%", help="Share of its emirate's salon sites it out-serves"),
            "Est. growth": st.column_config.NumberColumn(format="+%d%%", help="Net new women ÷ the women our lounges serve")})
