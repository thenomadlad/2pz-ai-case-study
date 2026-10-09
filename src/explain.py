"""Pyramid explanations: an answer (headline), 2-5 supporting arguments, 2-5 data points each.

Three kinds: a branch decision, an opportunity-area decision, and the network-wide
executive summary. The rubric / 2x2 make every decision, and `prioritize` decides which
arguments matter and in what order: importance is computed, never left to the AI. An LLM
then writes the pyramid from a fact sheet. Every cited {field, value} and every number in
its prose must match that fact sheet, and the arguments must be exactly the ranked topics
(`verify`), or it is regenerated once and then replaced by the deterministic template.
Explanations are cached by a hash of their fact sheet in a committed file, so the public
deploy shows AI output without an API key, and a stale entry can never be served for
changed numbers.

`uv run python -m src.explain` (just explain) regenerates the cache for the baseline.
"""
import hashlib
import json
import logging
import re
from dataclasses import dataclass

from src.config import REPO_ROOT, settings
from src.model import opportunity, rubric
from src.models import (
    BranchFeatures,
    CommunityFeatures,
    Decision,
    Evidence,
    Explanation,
    OpportunityDecision,
    Reason,
)

logger = logging.getLogger(__name__)

CACHE_PATH = REPO_ROOT / "data" / "explanations" / "cache.json"
PROMPT_VERSION = "v3"
MIN_ITEMS, MAX_ITEMS = 2, 5  # per pyramid level: enough to support, few enough to read


@dataclass(frozen=True)
class Field:
    label: str
    unit: str
    meaning: str
    pct: bool = False  # stored as 0-1, shown as %


GLOSSARY: dict[str, Field] = {
    # --- branch ---
    "female_pop_served": Field(
        "Female residents in catchment", "people",
        "Estimated women living in the communities closer to this branch than to any other "
        "Bedashing branch (straight-line). 49% of each community's census population."),
    "communities_served": Field(
        "Communities in catchment", "count",
        "Official Dubai communities whose nearest Bedashing branch is this one."),
    "contested_share": Field(
        "Cannibalisation", "% of catchment",
        "Share of the catchment's residents whose second-nearest Bedashing branch is almost "
        "as close as this one (within the contest ratio), so two branches compete for them.",
        pct=True),
    "nearest_sibling_km": Field(
        "Nearest other Bedashing branch", "km", "Straight-line distance to the closest sibling."),
    "competitors_in_catchment": Field(
        "Competitor salons in catchment", "count",
        "Women's beauty and hair salons (OpenStreetMap) in this branch's catchment "
        "communities. A lower bound: OSM misses some salons."),
    "competitors_per_10k": Field(
        "Competitive overlap", "salons per 10k women",
        "Competitor salons per 10,000 female residents. Higher means a more saturated market."),
    "rating": Field("Customer rating", "stars (of 5)", "Average review score on 2GIS."),
    "review_count": Field("Reviews", "count",
                          "Number of 2GIS reviews behind the rating; more means more reliable."),
    "composite": Field(
        "Composite score", "0-1",
        "Equal-weight average of the four signal scores below. "
        f"PROTECT ≥ {rubric.PROTECT_AT}, SHRINK ≤ {rubric.SHRINK_AT}."),
    **{f"score_{s.name}": Field(
        f"{s.name.capitalize()} score", "0-1",
        f"{s.label}, converted to a fixed 0-1 score where 1 is best for the branch "
        "(scale in the Threshold column).")
       for s in rubric.SIGNALS},
    # --- opportunity area ---
    "female_pop": Field(
        "Female residents", "people",
        "Estimated women living in this community: 49% of its census population."),
    "competitors": Field("Competitor salons", "count",
                         "Women's beauty and hair salons in this community (OpenStreetMap)."),
    "nearest_branch_id": Field("Nearest Bedashing branch", "", "The closest existing branch."),
    "nearest_branch_km": Field("Distance to nearest branch", "km", "Straight-line distance."),
    "hosts_branch": Field("Already has a branch", "yes/no",
                          "Whether a Bedashing branch already sits in this community."),
    "underserved": Field("Underserved", "yes/no",
                         f"Nearest branch more than {opportunity.FAR_KM:g} km away."),
    "unsaturated": Field(
        "Unsaturated", "yes/no",
        f"Fewer than {opportunity.UNSATURATED_PER_10K:g} competitor salons per 10k women."),
    "branches_here": Field("Bedashing branches here", "count",
                           "Bedashing branches located in this community."),
    "salons_supported": Field(
        "Salons this area could support", "salons",
        f"Women ÷ 10,000 × {opportunity.MEDIAN_SALONS_PER_10K:g}, the Dubai median density."),
    "salon_headroom": Field(
        "Room for more salons", "salons",
        "Salons it could support minus competitors and Bedashing branches already here "
        "(never below 0)."),
    "uncovered_women": Field(
        "Women not covered by Bedashing", "people",
        f"All the area's women when its nearest branch is over {opportunity.FAR_KM:g} km away; "
        "otherwise 0."),
    "fair_share": Field(
        "Bedashing fair share", "% of salons here",
        "Bedashing's share of the salons in this area. A naive capture estimate: it assumes "
        "every salon is equally attractive.", pct=True),
    "captured_women_est": Field("Women Bedashing captures (est.)", "people",
                                "Fair share × the area's women."),
    "far_km_threshold": Field("Underserved line", "km",
                              "Nearest branch further than this means underserved."),
    "unsaturated_threshold": Field("Saturation cut-off", "salons per 10k women",
                                   "Fewer competitors than this means unsaturated."),
    "min_pop_floor": Field("Population floor", "people",
                           "Fewer women than this is too small to carry a branch."),
    "worker_housing": Field(
        "Likely worker housing", "yes/no",
        "Industrial / investment-park community, where demand is overstated."),
    "estimated_female_share": Field(
        "Estimated female share", "%", "Uniform share applied to every community's census "
        "population; no per-community split is published.", pct=True),
    # --- network ---
    "branches_total": Field("Branches", "count", "Bedashing branches in Dubai."),
    "protect_count": Field("PROTECT", "branches", "Branches with composite ≥ 0.65."),
    "hold_count": Field("HOLD", "branches", "Branches between the two thresholds."),
    "shrink_count": Field("SHRINK", "branches", "Branches with composite ≤ 0.35."),
    "protect_branches": Field("PROTECT branches", "", "Ids of PROTECT branches."),
    "shrink_branches": Field("SHRINK branches", "", "Ids of SHRINK branches."),
    "protect_composite_min": Field("Weakest PROTECT composite", "0-1",
                                   "Lowest composite among PROTECT branches."),
    "shrink_composite_max": Field("Strongest SHRINK composite", "0-1",
                                  "Highest composite among SHRINK branches."),
    "low_confidence_count": Field(
        "Low-confidence calls", "branches",
        "Branches within 0.05 of a threshold, or with a missing input."),
    "areas_total": Field("Communities", "count", "Dubai communities evaluated."),
    "grow_count": Field("GROW", "areas", "Underserved, unsaturated communities."),
    "watch_count": Field("WATCH", "areas", "Communities passing one of the two tests."),
    "grow_areas": Field("GROW areas", "", "Ids of GROW communities."),
    "grow_nearest_km_min": Field("Closest GROW area to a branch", "km",
                                 "Smallest nearest-branch distance among GROW areas."),
    "grow_nearest_km_max": Field("Furthest GROW area from a branch", "km",
                                 "Largest nearest-branch distance among GROW areas."),
    "grow_competitors_per_10k_max": Field(
        "Most competitive GROW area", "salons per 10k women",
        "Highest competitive overlap among GROW areas."),
    "competitors_total": Field("Competitor salons mapped", "count",
                               "OpenStreetMap salons in the competitive set (a lower bound)."),
    "revenue_data_available": Field("Revenue data", "yes/no", "Per-branch revenue or footfall."),
    "rent_data_available": Field("Rent data", "yes/no", "Per-branch rent, capex or lease terms."),
}

BRANCH_TABLE = ("female_pop_served", "communities_served", "contested_share",
                "nearest_sibling_km", "competitors_in_catchment", "competitors_per_10k",
                "rating", "review_count", "composite", "score_demand",
                "score_cannibalisation", "score_competition", "score_quality")
OPPORTUNITY_TABLE = ("female_pop", "competitors", "competitors_per_10k", "branches_here",
                     "salons_supported", "salon_headroom", "uncovered_women", "fair_share",
                     "captured_women_est", "nearest_branch_id", "nearest_branch_km",
                     "hosts_branch", "underserved", "unsaturated")
# Fields that live on the OpportunityDecision rather than the CommunityFeatures.
_OPPORTUNITY_OUTPUTS = ("underserved", "unsaturated", "salons_supported", "salon_headroom",
                        "uncovered_women", "fair_share", "captured_women_est")

# Each argument a pyramid can make, with the facts that can back it. `prioritize` picks
# which apply and orders them; every reason must cite at least one of its topic's fields.
TOPICS: dict[str, dict[str, tuple[str, ...]]] = {
    "branch": {
        "demand": ("female_pop_served", "communities_served", "score_demand"),
        "cannibalisation": ("contested_share", "nearest_sibling_km", "score_cannibalisation"),
        "competition": ("competitors_per_10k", "competitors_in_catchment", "score_competition"),
        "quality": ("rating", "review_count", "score_quality"),
    },
    "opportunity": {
        "presence": ("hosts_branch", "nearest_branch_id", "nearest_branch_km"),
        "coverage": ("nearest_branch_km", "nearest_branch_id", "underserved",
                     "far_km_threshold"),
        "competition": ("competitors_per_10k", "competitors", "unsaturated",
                        "unsaturated_threshold"),
        "demand": ("female_pop", "min_pop_floor", "hosts_branch"),
        "headroom": ("salon_headroom", "salons_supported", "competitors", "branches_here",
                     "uncovered_women"),
        "worker_housing": ("worker_housing", "estimated_female_share", "female_pop"),
    },
    "network": {
        "shrink": ("shrink_count", "shrink_branches", "shrink_composite_max"),
        "grow": ("grow_count", "grow_areas", "grow_nearest_km_min", "grow_nearest_km_max",
                 "grow_competitors_per_10k_max"),
        "protect": ("protect_count", "protect_branches", "protect_composite_min"),
        "confidence": ("hold_count", "low_confidence_count", "branches_total"),
        "data_gaps": ("revenue_data_available", "rent_data_available", "competitors_total"),
    },
}
TOPIC_LABELS = {
    "demand": "Demand", "cannibalisation": "Cannibalisation", "competition": "Competition",
    "quality": "Customer quality", "presence": "Existing branch", "coverage": "Coverage",
    "headroom": "Room left",
    "worker_housing": "Demand reliability", "shrink": "Where to cut back",
    "grow": "Where to grow", "protect": "What to protect", "confidence": "How sure we are",
    "data_gaps": "What this can't see",
}
IMPORTANT = 0.1  # a branch signal must sit this far from neutral (0.5) to be an argument


def fmt(field: str, value) -> str:
    f = GLOSSARY.get(field)
    if value is None:
        return "n/a (missing)"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if f and f.pct:
        return f"{value * 100:.0f}%"
    if isinstance(value, float):
        return f"{value:,.2f}".rstrip("0").rstrip(".") if abs(value) < 100 else f"{value:,.0f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def fmt_unit(field: str, value) -> str:
    """Value with its unit, for prose and evidence lines ("2.72 km", "87% of catchment")."""
    f = GLOSSARY.get(field)
    text = fmt(field, value)
    if (not f or value is None or isinstance(value, bool)
            or f.unit in ("", "count", "yes/no", "0-1", "%")):
        return text
    return f"{text} of catchment" if f.pct else f"{text} {f.unit}"


def _scale(signal) -> str:
    return (f"{signal.name.capitalize()} score: {fmt_unit(signal.field, signal.worst)} → 0, "
            f"{fmt_unit(signal.field, signal.best)} → 1")


# The decision rule each factor feeds, built from the model's own constants.
THRESHOLDS: dict[str, str] = {
    **{s.field: _scale(s) for s in rubric.SIGNALS},
    **{f"score_{s.name}": "One quarter of the composite" for s in rubric.SIGNALS},
    "contested_share": (f"{_scale(next(s for s in rubric.SIGNALS if s.name == 'cannibalisation'))}"
                        f"; contested when the 2nd-nearest branch is within "
                        f"{settings.contest_ratio}× the nearest"),
    "composite": f"PROTECT ≥ {rubric.PROTECT_AT} · HOLD between · SHRINK ≤ {rubric.SHRINK_AT}",
    "female_pop": f"At least {opportunity.MIN_POP:,} women to be a candidate",
    "nearest_branch_km": f"Underserved if over {opportunity.FAR_KM:g} km",
    "hosts_branch": "SKIP if yes",
    "salons_supported": f"At {opportunity.MEDIAN_SALONS_PER_10K:g} salons per 10k women",
    "salon_headroom": "Positive when the area is below the median density",
    "uncovered_women": f"Counted when the nearest branch is over {opportunity.FAR_KM:g} km away",
    "fair_share": "Naive: every salon equally attractive",
    "underserved": "GROW needs both tests, WATCH one, SKIP neither",
    "unsaturated": "GROW needs both tests, WATCH one, SKIP neither",
}


# Where an area's rule for a shared field differs from the branch rule.
AREA_THRESHOLDS = {
    "competitors_per_10k": f"Unsaturated if under {opportunity.UNSATURATED_PER_10K:g}",
}


def table_rows(fields: tuple[str, ...], facts: dict, kind: str = "branch") -> list[dict]:
    rules = {**THRESHOLDS, **(AREA_THRESHOLDS if kind == "opportunity" else {})}
    return [{"Factor": GLOSSARY[k].label, "Value": fmt(k, facts.get(k)),
             "Unit": GLOSSARY[k].unit, "Threshold": rules.get(k, "—"),
             "What it means": GLOSSARY[k].meaning}
            for k in fields]


def _rounded(facts: dict) -> dict:
    return {k: round(v, 4) if isinstance(v, float) else v for k, v in facts.items()}


def branch_facts(f: BranchFeatures, d: Decision) -> dict:
    facts = {k: getattr(f, k) for k in BRANCH_TABLE if hasattr(f, k)}
    facts.update(composite=d.composite, **{f"score_{k}": v for k, v in d.scores.items()})
    return _rounded(facts)


def opportunity_facts(c: CommunityFeatures, o: OpportunityDecision) -> dict:
    facts = {k: getattr(c, k) for k in OPPORTUNITY_TABLE if hasattr(c, k)}
    facts.update({k: getattr(o, k) for k in _OPPORTUNITY_OUTPUTS})
    facts.update(
        far_km_threshold=opportunity.FAR_KM,
        unsaturated_threshold=opportunity.UNSATURATED_PER_10K,
        min_pop_floor=opportunity.MIN_POP,
        worker_housing=bool(opportunity.WORKER_HOUSING.search(c.name)),
        estimated_female_share=settings.global_female_share,
    )
    return _rounded(facts)


def network_facts(decisions: list[Decision], opportunities: list[OpportunityDecision],
                  communities: list[CommunityFeatures], competitors_total: int) -> dict:
    by_action = {a: [d for d in decisions if d.action == a]
                 for a in ("PROTECT", "HOLD", "SHRINK")}
    grow_ids = {o.community_id for o in opportunities if o.action == "GROW"}
    grow = [c for c in communities if c.community_id in grow_ids]
    return _rounded({
        "branches_total": len(decisions),
        "protect_count": len(by_action["PROTECT"]),
        "hold_count": len(by_action["HOLD"]),
        "shrink_count": len(by_action["SHRINK"]),
        "protect_branches": ", ".join(sorted(d.branch_id for d in by_action["PROTECT"])) or "none",
        "shrink_branches": ", ".join(sorted(d.branch_id for d in by_action["SHRINK"])) or "none",
        "protect_composite_min": min((d.composite for d in by_action["PROTECT"]), default=None),
        "shrink_composite_max": max((d.composite for d in by_action["SHRINK"]), default=None),
        "low_confidence_count": sum(d.confidence == "low" for d in decisions),
        "areas_total": len(opportunities),
        "grow_count": len(grow),
        "watch_count": sum(o.action == "WATCH" for o in opportunities),
        "grow_areas": ", ".join(sorted(grow_ids)) or "none",
        "grow_nearest_km_min": min((c.nearest_branch_km for c in grow), default=None),
        "grow_nearest_km_max": max((c.nearest_branch_km for c in grow), default=None),
        "grow_competitors_per_10k_max": max((c.competitors_per_10k for c in grow), default=None),
        "competitors_total": competitors_total,
        "revenue_data_available": False,
        "rent_data_available": False,
    })


# --- prioritization: which arguments, in what order --------------------------------------

def prioritize(kind: str, facts: dict, action: str) -> list[str]:
    """The 2-5 arguments that matter most for this decision, most important first."""
    if kind == "branch":
        # Importance = how far a signal sits from neutral, in the direction of the call:
        # strengths for PROTECT, weaknesses for SHRINK, either for HOLD.
        sign = {"PROTECT": 1, "SHRINK": -1}.get(action)

        def weight(topic: str) -> float:
            delta = facts[f"score_{topic}"] - 0.5
            return delta * sign if sign else abs(delta)

        ranked = sorted(TOPICS["branch"], key=weight, reverse=True)
        chosen = [t for t in ranked if weight(t) >= IMPORTANT]
        return (chosen + [t for t in ranked if t not in chosen])[:max(MIN_ITEMS, len(chosen))]
    if kind == "opportunity":
        if facts["hosts_branch"]:
            return ["presence", "competition", "headroom"]
        if facts["female_pop"] < facts["min_pop_floor"]:
            return ["demand", "coverage", "competition"]
        topics = ["coverage", "competition", "headroom", "demand"]
        if facts["worker_housing"] and facts["underserved"] and facts["unsaturated"]:
            topics.append("worker_housing")
        return topics
    skip = {"shrink": facts["shrink_count"] == 0, "grow": facts["grow_count"] == 0,
            "protect": facts["protect_count"] == 0}
    return [t for t in TOPICS["network"] if not skip.get(t)][:MAX_ITEMS]


def _thresholds_note(kind: str) -> str:
    if kind == "network":
        return f"{rubric.THRESHOLDS_WHY} {opportunity.THRESHOLDS_WHY}"
    return rubric.THRESHOLDS_WHY if kind == "branch" else opportunity.THRESHOLDS_WHY


def _ev(field: str, facts: dict) -> Evidence:
    return Evidence(field=field, label=GLOSSARY[field].label, value=facts.get(field))


# --- template (no AI) ---------------------------------------------------------------

def _template_claim(kind: str, topic: str, f: dict) -> str:
    if kind == "branch":
        score = f[f"score_{topic}"]
        strength = "a strength" if score >= 0.6 else "a weakness" if score <= 0.4 else "middling"
        main = TOPICS["branch"][topic][0]
        return f"{GLOSSARY[main].label} is {strength}: {fmt_unit(main, f[main])}."
    if kind == "opportunity":
        return {
            "presence": f"Already served: Bedashing has a branch here ({f['nearest_branch_id']}).",
            "coverage": (f"Nearest branch {f['nearest_branch_id']} is "
                         f"{fmt('nearest_branch_km', f['nearest_branch_km'])} km away, "
                         f"{'beyond' if f['underserved'] else 'within'} the "
                         f"{f['far_km_threshold']:g} km line."),
            "competition": (f"{fmt('competitors_per_10k', f['competitors_per_10k'])} competitor "
                            f"salons per 10k women, {'below' if f['unsaturated'] else 'above'} "
                            f"the {f['unsaturated_threshold']:g} cut-off."),
            "demand": (f"About {fmt('female_pop', f['female_pop'])} women live here "
                       f"(floor {fmt('min_pop_floor', f['min_pop_floor'])})."),
            "headroom": (f"Room for {f['salon_headroom']} more salons: it could support about "
                         f"{fmt('salons_supported', f['salons_supported'])} and has "
                         f"{f['competitors']} competitors plus {f['branches_here']} Bedashing "
                         f"branch{'' if f['branches_here'] == 1 else 'es'}."),
            "worker_housing": ("Likely worker housing: the uniform female-share estimate "
                               "overstates demand here, so the call is capped at WATCH."),
        }[topic]
    return {
        "shrink": f"Investigate before shrinking: {f['shrink_branches']}.",
        "grow": (f"{f['grow_count']} areas to GROW, each "
                 f"{fmt('grow_nearest_km_min', f['grow_nearest_km_min'])}-"
                 f"{fmt('grow_nearest_km_max', f['grow_nearest_km_max'])} km from a branch."),
        "protect": f"Protect {f['protect_branches']}.",
        "confidence": (f"{f['hold_count']} branches sit in the HOLD band and "
                       f"{f['low_confidence_count']} calls are low confidence."),
        "data_gaps": ("No revenue or rent data: these are location and market calls, not "
                      "return-on-capital calls."),
    }[topic]


def _template_headline(kind: str, action: str, f: dict) -> str:
    if kind == "branch":
        return (f"{action}: composite {f['composite']:.2f} (PROTECT at {rubric.PROTECT_AT} or "
                f"more, SHRINK at {rubric.SHRINK_AT} or less).")
    if kind == "opportunity":
        return (f"{action}: {'underserved' if f['underserved'] else 'covered'} and "
                f"{'unsaturated' if f['unsaturated'] else 'saturated'}.")
    return (f"{f['protect_count']} PROTECT, {f['hold_count']} HOLD and {f['shrink_count']} "
            f"SHRINK across {f['branches_total']} branches, with {f['grow_count']} areas to "
            "GROW.")


_TEMPLATE_CAPTIONS = {
    "branch": ("Each signal is scored 0-1 on a fixed scale, where 1 is good for the branch, "
               "and the composite is their equal-weight average. Demand counts the women "
               "nearest this branch, cannibalisation counts how many of them a sibling branch "
               "also competes for, competitive overlap counts rival salons per 10k women, and "
               "quality is the customer rating."),
    "opportunity": ("An area is underserved when the nearest Bedashing branch is far away, and "
                    "unsaturated when it has few rival salons for its population. GROW needs "
                    "both, WATCH has one, and SKIP has neither."),
    "network": ("Branch calls come from a fixed-scale rubric; area calls come from two tests, "
                "distance to the nearest branch and competitor density."),
}


def template_explanation(kind: str, subject_id: str, action: str, facts: dict) -> Explanation:
    topics = prioritize(kind, facts, action)
    reasons = [Reason(topic=t, claim=_template_claim(kind, t, facts),
                      evidence=[_ev(k, facts) for k in TOPICS[kind][t][:MAX_ITEMS]])
               for t in topics]
    return Explanation(subject_id=subject_id, kind=kind, action=action,
                       headline=_template_headline(kind, action, facts), reasons=reasons,
                       table_caption=_TEMPLATE_CAPTIONS[kind],
                       thresholds_note=_thresholds_note(kind), source="template")


# --- grounding check ------------------------------------------------------------------

_NUMBER = re.compile(r"(?<![\w.])-?\d[\d,]*\.?\d*")  # "0-1" is a range, not -1


def _allowed_numbers(facts: dict) -> list[float]:
    nums = [float(v) for v in facts.values()
            if isinstance(v, (int, float)) and not isinstance(v, bool)]
    nums += [v * 100 for v in nums if 0 <= v <= 1]  # shares and scores quoted as %
    nums += [rubric.PROTECT_AT, rubric.SHRINK_AT, 4, 0, 1]
    nums += [x for s in rubric.SIGNALS for x in (s.worst, s.best)]
    nums += [opportunity.FAR_KM, opportunity.UNSATURATED_PER_10K, opportunity.MIN_POP]
    nums += [2, 3, 10, 10_000, 100, 5]  # "per 10k", "2GIS", "out of 5"
    return nums


def _close(a: float, b: float) -> bool:
    # Within 0.5% (e.g. "42,600" for 42,648), or b rounded to a whole number ("33%" for
    # 33.4) -- but never a near-miss like 99 for 100.
    return abs(a - b) <= max(0.005 * abs(b), 0.011) or (a == int(a) and round(b) == a)


def _match(cited, actual) -> bool:
    if isinstance(actual, bool) or isinstance(cited, bool):
        return cited == actual
    if isinstance(actual, (int, float)) and isinstance(cited, (int, float)):
        return _close(float(cited), float(actual))
    return str(cited).strip().lower() == str(actual).strip().lower()


def verify(exp: Explanation, facts: dict, kind: str) -> list[str]:
    errors = []
    topics = prioritize(kind, facts, exp.action)
    got = [r.topic for r in exp.reasons]
    if got != topics:
        errors.append(f"arguments must be exactly {topics}, in that order; got {got}")
    allowed = _allowed_numbers(facts)
    for r in exp.reasons:
        if not MIN_ITEMS <= len(r.evidence) <= MAX_ITEMS:
            errors.append(f"argument {r.topic!r} has {len(r.evidence)} data points, "
                          f"expected {MIN_ITEMS}-{MAX_ITEMS}")
        own = TOPICS[kind].get(r.topic, ())
        if own and not any(e.field in own for e in r.evidence):
            errors.append(f"argument {r.topic!r} must cite at least one of {list(own)}")
        for e in r.evidence:
            if e.field not in facts:
                errors.append(f"unknown field {e.field!r}")
            elif not _match(e.value, facts[e.field]):
                errors.append(f"{e.field}: cited {e.value!r}, actual {facts[e.field]!r}")
    # Ids like "mirdif-35" are cited verbatim; drop them so their digits aren't read as data.
    ids = sorted({part for v in facts.values() if isinstance(v, str) for part in v.split(", ")},
                 key=len, reverse=True)
    for text in [exp.headline, exp.table_caption] + [r.claim for r in exp.reasons]:
        for ident in ids:
            text = re.sub(re.escape(ident), "", text, flags=re.IGNORECASE)
        for raw in _NUMBER.findall(text):
            raw = raw.replace(",", "").rstrip(".")
            n = float(raw)
            # Compare at the precision the text uses: "3.1" matches 3.06, "33%" matches 33.4,
            # "4,400" matches 4,431 (trailing zeros = rounded to the hundreds).
            places = len(raw.split(".")[1]) if "." in raw else 0
            if not places and n:
                places = -(len(raw.lstrip("-")) - len(raw.lstrip("-").rstrip("0")))
            # Exactly the fact, correctly rounded: no near-misses like 42,500 for 42,648.
            if not any(round(a, places) == n for a in allowed):
                errors.append(f"number {raw} in text not in fact sheet")
    return errors


# --- LLM --------------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You explain retail network decisions for Bedashing Beauty Lounge's portfolio team, who "
    "will defend them to the COO and a private-equity board. The decision is already made by "
    "a rule-based model; you explain it, you never change it. Write a pyramid: a one-sentence "
    "answer (headline), then the supporting arguments you are given, in the order given, each "
    "a one-sentence claim backed by 2-5 data points copied from the fact sheet. Use only the "
    "fact sheet. Every number you write must appear in the fact sheet or the thresholds; "
    "round sensibly. Write like a board memo: short, concrete claims. Never mention revenue, "
    "rent or profit figures (none exist). Always answer by calling the submit_explanation tool."
)
# Server-side refusal fallback: a declined request is re-run on Anthropic's recommended
# substitute model inside the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

# strict: the API guarantees inputs match this schema. Strict mode doesn't support array
# length limits, so the 2-5 counts and argument order are enforced by verify() instead.
EXPLAIN_TOOL = {
    "name": "submit_explanation",
    "strict": True,
    "description": "Submit the pyramid: a headline answer, the given arguments in order "
                   "(2-5 data points each, copied from the fact sheet), and a table caption.",
    "input_schema": {
        "type": "object",
        "properties": {
            "headline": {"type": "string",
                         "description": "The answer in one sentence, for an executive."},
            "reasons": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string",
                                  "description": "The argument's topic key, as given."},
                        "claim": {"type": "string", "description": "One sentence."},
                        "evidence": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "field": {"type": "string",
                                              "description": "A key from the fact sheet."},
                                    "value": {
                                        "anyOf": [{"type": "number"}, {"type": "string"},
                                                  {"type": "boolean"}, {"type": "null"}],
                                        "description": "That key's exact value.",
                                    },
                                },
                                "required": ["field", "value"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["topic", "claim", "evidence"],
                    "additionalProperties": False,
                },
            },
            "table_caption": {
                "type": "string",
                "description": "2-3 sentences explaining, for a non-technical executive, what "
                               "the factors measure and how to read them for this branch, "
                               "area or network.",
            },
        },
        "required": ["headline", "reasons", "table_caption"],
        "additionalProperties": False,
    },
}


def _user_message(kind: str, subject_id: str, action: str, facts: dict, errors: list[str]) -> str:
    msg = {
        "subject": f"{kind} {subject_id}",
        "decision": action,
        "arguments_in_order": [
            {"topic": t, "label": TOPIC_LABELS[t], "cite_at_least_one_of": TOPICS[kind][t]}
            for t in prioritize(kind, facts, action)],
        "fact_sheet": facts,
        "field_glossary": {k: {"label": GLOSSARY[k].label, "unit": GLOSSARY[k].unit,
                               "meaning": GLOSSARY[k].meaning} for k in facts},
        "thresholds": _thresholds_note(kind),
    }
    if errors:
        msg["your_previous_attempt_failed_checks"] = errors
    return json.dumps(msg)


def _parse(raw: dict, kind: str, subject_id: str, action: str) -> Explanation:
    def label(field: str) -> str:
        return GLOSSARY[field].label if field in GLOSSARY else field

    return Explanation(
        subject_id=subject_id, kind=kind, action=action, headline=raw["headline"],
        reasons=[Reason(topic=r["topic"], claim=r["claim"],
                        evidence=[Evidence(field=e["field"], label=label(e["field"]),
                                           value=e.get("value")) for e in r["evidence"]])
                 for r in raw["reasons"]],
        table_caption=raw["table_caption"], thresholds_note=_thresholds_note(kind),
        source="ai")


def llm_explanation(client, kind: str, subject_id: str, action: str,
                    facts: dict) -> Explanation | None:
    errors: list[str] = []
    for _attempt in range(2):
        try:
            # Opus 5.5 rejects forced tool_choice and temperature, and thinking is always
            # on: steer to the tool from the prompt, keep effort low (explaining a decision
            # already made), and leave max_tokens room for thinking.
            response = client.beta.messages.create(
                model=settings.anthropic_model, max_tokens=8000,
                output_config={"effort": "low"},
                betas=[FALLBACK_BETA], fallbacks="default",
                system=SYSTEM_PROMPT, tools=[EXPLAIN_TOOL],
                messages=[{"role": "user",
                           "content": _user_message(kind, subject_id, action, facts, errors)}],
            )
            if response.stop_reason == "refusal":
                logger.warning("explain: %s %s refused (%s)", kind, subject_id,
                               getattr(response.stop_details, "category", None))
                return None
            tool_use = next((b for b in response.content if b.type == "tool_use"), None)
            if tool_use is None:
                errors = ["You answered in text. Call the submit_explanation tool instead."]
                continue
            exp = _parse(tool_use.input, kind, subject_id, action)
        except Exception as exc:  # noqa: BLE001 - any API/shape failure -> template
            logger.warning("explain: LLM call failed for %s %s: %s", kind, subject_id, exc)
            return None
        errors = verify(exp, facts, kind)
        if not errors:
            return exp
        logger.warning("explain: %s %s failed grounding check: %s", kind, subject_id, errors)
    return None


# --- cache + entry point ---------------------------------------------------------------

def cache_key(kind: str, subject_id: str, action: str, facts: dict) -> str:
    payload = json.dumps({"v": PROMPT_VERSION, "model": settings.anthropic_model, "kind": kind,
                          "id": subject_id, "action": action, "facts": facts}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def load_cache() -> dict[str, dict]:
    return json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}


def explain(kind: str, subject_id: str, action: str, facts: dict,
            cache: dict[str, dict] | None = None, client=None) -> Explanation:
    """Cached AI explanation if this exact fact sheet was explained before, else a live LLM
    call when a client is given, else the template. Never writes the cache file."""
    cache = load_cache() if cache is None else cache
    key = cache_key(kind, subject_id, action, facts)
    if key in cache:
        return Explanation(**cache[key])
    if client is not None:
        exp = llm_explanation(client, kind, subject_id, action, facts)
        if exp is not None:
            cache[key] = exp.model_dump()
            return exp
    return template_explanation(kind, subject_id, action, facts)


NETWORK_ID, NETWORK_ACTION = "dubai", "SUMMARY"


def subjects_for(data) -> list[tuple[str, str, str, dict]]:
    """(kind, id, action, facts) for every explanation the app shows for this data."""
    subjects = [("network", NETWORK_ID, NETWORK_ACTION,
                 network_facts(data.decisions, data.opportunities, data.community_features,
                               len(data.competitors)))]
    subjects += [("branch", f.branch_id, data.decision_for(f.branch_id).action,
                  branch_facts(f, data.decision_for(f.branch_id))) for f in data.features]
    opp = {o.community_id: o for o in data.opportunities}
    subjects += [("opportunity", c.community_id, opp[c.community_id].action,
                  opportunity_facts(c, opp[c.community_id])) for c in data.community_features]
    return subjects


def make_client():
    """Client from ANTHROPIC_API_KEY, or None when it isn't set."""
    if not settings.anthropic_api_key:
        return None
    import anthropic
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def main() -> None:
    """Regenerate AI explanations for the current baseline and write the committed cache."""
    import anthropic

    from src.webapp.data import load_baseline

    client = make_client()
    if client is None:
        raise SystemExit("Set ANTHROPIC_API_KEY in .env first.")
    # Batch job: let the SDK's exponential backoff (honours retry-after) ride out per-minute
    # rate limits. Calls are sequential, so no concurrency limit is needed.
    client = client.with_options(max_retries=8)
    # Fail loudly before the batch. explain() swallows API errors so the app degrades to
    # templates, which here would silently write an empty cache.
    try:
        client.with_options(max_retries=2).messages.create(
            model=settings.anthropic_model, max_tokens=16,
            messages=[{"role": "user", "content": "Reply OK."}])
    except anthropic.RateLimitError as exc:
        raise SystemExit("Preflight still rate-limited (429) after retries; try again "
                         "shortly or check the key's rate limits in the console.") from exc
    except anthropic.APIStatusError as exc:
        raise SystemExit(f"Preflight failed ({exc.status_code}): {exc.message}") from exc
    subjects = subjects_for(load_baseline(settings))
    # Reuse entries whose exact facts are unchanged and that still pass today's checks, so
    # a re-run only fills gaps. Entries for subjects that no longer match are dropped below.
    old = load_cache()
    cache = {}
    for kind, sid, action, facts in subjects:
        key = cache_key(kind, sid, action, facts)
        if key in old and not verify(Explanation(**old[key]), facts, kind):
            cache[key] = old[key]
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

    def save() -> None:
        CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False, sort_keys=True))

    save()  # drops stale entries now, so an interrupted run never serves them
    ai = 0
    for i, (kind, sid, action, facts) in enumerate(subjects, start=1):
        had = len(cache)
        ai += explain(kind, sid, action, facts, cache=cache, client=client).source == "ai"
        if len(cache) > had:
            save()  # after every new explanation: an interrupted run keeps its progress
            print(f"explain: {i}/{len(subjects)} {kind} {sid}", flush=True)
    print(f"explain: {ai}/{len(subjects)} AI explanations passed grounding; "
          f"{len(subjects) - ai} fall back to template. Wrote {CACHE_PATH}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
