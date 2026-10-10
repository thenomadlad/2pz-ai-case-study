"""Rendering pieces shared by the pages: the what-if banner, explanations, tables, caveats and the
"before you trust these calls" box."""
from functools import cache

import pandas as pd
import streamlit as st

from src import explain
from src.baseline import Run
from src.model import growth, scorecard
from src.models import Area, AreaDecision, Decision, Explanation, Levels, LoungeFeatures
from src.webapp import data

BADGE_COLORS = {"PROTECT": "green", "HOLD": "orange", "SHRINK": "red", "NOT SCORED": "gray",
                "GROW": "blue", "WATCH": "violet", "SKIP": "gray"}
AFFLUENCE_NAMES = {"low": "off", "medium": "medium", "high": "strong"}
AFFLUENCE_KNOWN = 0.5   # under this share of women with an observed rent, affluence is mostly unknown
FEW_REVIEWS = 300   # under this many lifetime reviews, capture understates a lounge (noya-plaza: 215)


# --- what-if labels and banner ------------------------------------------------------------

def level_label(axis: str, level: str) -> str:
    """"15 min (medium)", "60% of premium reviews (medium)", "5.5% women (medium)",
    "medium: rent^0.5 (medium)"."""
    a = data.assumptions()
    if axis == "travel":
        return f"{a.travel_time_minutes[level]} min ({level})"
    if axis == "coverage":
        return f"{a.competitor_coverage[level]:.0%} of premium reviews ({level})"
    if axis == "affluence":
        e = a.affluence_elasticity[level]
        return f"{AFFLUENCE_NAMES[level]}" + (f": rent^{e:g}" if e else "") + f" ({level})"
    return f"{a.worker_housing_female_share[level]:.1%} women ({level})"


def what_if_summary() -> str:
    w, base, parts = data.what_if(), Levels(), []
    for axis, name in (("travel", "travel time"), ("coverage", "competitor coverage"),
                       ("worker_share", "worker-housing women"), ("affluence", "affluence weighting")):
        if getattr(w["levels"], axis) != getattr(base, axis):
            parts.append(f"{name} {level_label(axis, getattr(w['levels'], axis))}")
    if w["recall"] is not None:
        parts.append(f"search recall {w['recall']:.2f}")
    if w["closed"]:
        parts.append("closed: " + ", ".join(sorted(w["closed"])))
    return "; ".join(parts)


def banner() -> None:
    if data.active():
        st.warning(f"**What-if view**, not the baseline: {what_if_summary()}. Reset it in the "
                   "Overview's what-if panel.", icon="🧪")


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


def render_factor_table(exp: Explanation, fields: tuple[str, ...], facts: dict) -> None:
    st.caption(exp.table_caption)
    wrapped_table(explain.table_rows(fields, facts))


def url_picker(label: str, param: str, options: list[str], format_func, key: str) -> str:
    """A selectbox driven by ?param=. The URL is the source of truth: the keyed widget is set
    from it before rendering and writes back only on a real user change."""
    wanted = st.query_params.get(param)
    st.session_state[key] = wanted if wanted in options else options[0]

    def _picked() -> None:
        st.query_params[param] = st.session_state[key]

    return st.selectbox(label, options, key=key, on_change=_picked, format_func=format_func)


# --- limitations and caveats --------------------------------------------------------------

def limitations_box(r: Run) -> None:
    """The biggest limitations, right under the executive summary."""
    from src.webapp import nav

    scored = [d for d in r.decisions if d.action != "NOT SCORED"]
    low = sum(d.confidence == "low" for d in scored)
    act = {d.area_id: d.action for d in r.area_decisions}
    grow = [a for a in r.areas if act[a.area_id] == "GROW"]
    sharjah = sum(a.emirate == "Sharjah" for a in grow)
    with st.container(border=True):
        st.markdown("#### ⚠️ Before you trust these calls")
        st.markdown(
            "These calls are a shortlist to test with the business, not decisions.\n\n"
            "1. **No money in the model.** No revenue, rent, capex or lease data: it scores location "
            "and market position only. SHRINK means *investigate*, not *close*; a SHRINK lounge can be "
            "profitable and a PROTECT one unprofitable.\n"
            "2. **Capture comes from lifetime Google reviews.** Older salons look bigger, so new lounges "
            "(noya-plaza, 215 reviews) look weak partly because they are new. Reviews are a proxy for "
            "customers, not a count.\n"
            "3. **Affluence is observed in Dubai only.** Demand weights each woman by her cell's median "
            f"household rent (DLD, 3 months), and only {len(data.rents())} Dubai cells have one: every lounge and growth "
            "area outside Dubai is weighted neutral, so Dubai-vs-elsewhere comparisons mix weighted and "
            "unweighted demand. Rent is not income or salon spend.\n"
            f"4. **The calls depend on the assumptions.** Right now **{low} of {len(scored)}** scored "
            "lounges are low confidence: near a threshold, a thin market, no rating gap (missing rating or no rated substitutes), or a call "
            f"that changes in {scorecard.FLIP_LOW}+ of the {scorecard.COMBOS} assumption combinations. Try the what-if "
            "panel below.\n"
            f"5. **Growth areas are a first cut.** Competitor data is partial and the saturation line "
            f"was set from the data it judges. {sharjah} of {len(grow)} GROW areas are in Sharjah "
            "emirate but beyond a 15-minute drive of Bedashing's two Sharjah lounges (al-jada, zawaya-walk), "
            "both on the Dubai side. Why the footprint there is only two lounges is a business question: "
            "the model can't see licensing, brand fit, landlord terms or customer mix.")
        st.page_link(nav.HOW, label="All the limitations, every assumption and threshold →", icon="⚠️")


def near_threshold(d: Decision) -> str | None:
    for name, line in (("PROTECT", scorecard.PROTECT_AT), ("SHRINK", scorecard.SHRINK_AT)):
        if abs(d.composite - line) < scorecard.LOW_MARGIN:
            return (f"Composite {d.composite:.2f} is within {scorecard.LOW_MARGIN} of the {name} line ({line}): a small "
                    "change in any input moves the call.")
    return None


def lounge_caveats(f: LoungeFeatures, d: Decision, flips: int | None) -> list[str]:
    """Everything that weakens this lounge's call, most specific first."""
    if d.action == "NOT SCORED":
        return [d.rationale, ("It stays on the map, and its catchment still counts as reached for "
                              "the growth areas.")]
    out = [c for c in (near_threshold(d),) if c] + d.caveats[1:]
    if flips and flips < scorecard.FLIP_LOW:
        out.append(f"The call changes in {flips} of {scorecard.COMBOS} assumption combinations (low "
                   f"confidence from {scorecard.FLIP_LOW}).")
    if f.affluence_coverage < AFFLUENCE_KNOWN:
        out.append(affluence_caveat(f.affluence_coverage))
    if f.review_count < FEW_REVIEWS:
        out.append(f"Only {f.review_count:,} lifetime Google reviews. Capture uses lifetime reviews, "
                   "so a newer lounge looks weaker than it is.")
    if f.branch_id == "mirdif-35":
        out.append("Market overstated: worker housing not mapped as industrial in OpenStreetMap "
                   "(Dubai Investment Park, very likely Sonapur) counts as ordinary housing here.")
    return out + d.caveats[:1]      # no money in the model, last: it applies to every lounge


def area_caveats(a: Area, d: AreaDecision) -> list[str]:
    out = list(d.caveats)
    if a.premium_reviews_per_1k is not None and growth.MIN_COVERAGE <= a.data_coverage < 0.99:
        out.append(f"Competitor data covers {a.data_coverage:.0%} of the women here; saturation is "
                   "computed over the searched cells only.")
    if a.premium_reviews_per_1k is not None and abs(a.premium_reviews_per_1k - growth.UNSATURATED_PER_1K) < 10:
        out.append(f"Near the saturation line ({a.premium_reviews_per_1k:.0f} vs "
                   f"{growth.UNSATURATED_PER_1K:g} premium reviews per 1k women), and that line was "
                   "set from the data it judges.")
    if a.affluence_coverage < AFFLUENCE_KNOWN and not any("Affluence" in c for c in out):
        out.append(affluence_caveat(a.affluence_coverage))
    if a.worker_share >= 0.25:
        out.append(f"{a.worker_share:.0%} of adults live in worker housing: the women estimate rests "
                   "on the worker-housing female share assumption.")
    if a.emirate == "Sharjah":
        out.append(f"Bedashing's only Sharjah lounges (al-jada, zawaya-walk) are on the Dubai side; "
                   f"this area is beyond the drive time of both ({a.nearest_lounge_id} is nearest). Why the "
                   "footprint is only two lounges is a business question: the model can't see licensing, "
                   "brand fit, landlord terms or customer mix.")
    out.append(f"Distance to the nearest lounge ({a.nearest_lounge_km:.1f} km to {a.nearest_lounge_id}) "
               "is a straight line, not a drive.")
    return out


def affluence_caveat(coverage: float) -> str:
    if not coverage:
        return "No observed rents outside Dubai: weighted neutral."
    return (f"Affluence unknown here: weighted neutral. Only {coverage:.0%} of these women live in "
            f"cells with an observed rent (DLD rents cover {len(data.rents())} Dubai cells; nowhere else), "
            "so the rest count as average.")


def affluence_metrics(raw: float, addressable: float, rent: float | None, coverage: float) -> None:
    """Raw vs addressable women, the affluence rent and how much of it is observed."""
    cols = st.columns(3)
    cols[0].metric("Women 15+ (raw)", f"{raw:,.0f}")
    cols[1].metric("Addressable women", f"{addressable:,.0f}", f"{addressable / raw - 1:+.0%}" if raw else None,
                   delta_color="off")
    cols[1].caption("Weighted by affluence: the demand that counts.")
    cols[2].metric("Affluence rent (median, AED/yr)", "no data" if rent is None else f"{rent:,.0f}")
    cols[2].caption(f"{coverage:.0%} of the women live in cells with an observed Dubai rent; "
                    "the rest are weighted neutral.")


def render_caveats(title: str, items: list[str], strong: bool) -> None:
    """Caveats as a visible box: a warning when they weaken the call, else an info box."""
    (st.warning if strong else st.info)(f"**{title}**\n\n" + "\n".join(f"- {c}" for c in items))
