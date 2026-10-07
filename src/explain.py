"""Explanations for branch and opportunity decisions: 3 reasons x 2-3 data points each,
plus a caption for the factor table.

The rubric / 2x2 make every decision; this module only explains them. An LLM writes the
explanation from a fact sheet. Every cited {field, value} and every number in its prose
must match that fact sheet (`verify`), or it is regenerated once and then replaced by
the deterministic template. Explanations are cached by a hash of their fact sheet in a
committed file, so the public deploy shows AI output without an API key, and a stale
entry can never be served for changed numbers.

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
PROMPT_VERSION = "v2"


@dataclass(frozen=True)
class Field:
    label: str
    unit: str
    meaning: str
    pct: bool = False  # stored as 0-1, shown as %


GLOSSARY: dict[str, Field] = {
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
        f"{s.label} on a fixed scale: {s.worst:g} scores 0, {s.best:g} scores 1.")
       for s in rubric.SIGNALS},
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
}

BRANCH_TABLE = ("female_pop_served", "communities_served", "contested_share",
                "nearest_sibling_km", "competitors_in_catchment", "competitors_per_10k",
                "rating", "review_count", "composite", "score_demand",
                "score_cannibalisation", "score_competition", "score_quality")
OPPORTUNITY_TABLE = ("female_pop", "competitors", "competitors_per_10k", "nearest_branch_id",
                     "nearest_branch_km", "hosts_branch", "underserved", "unsaturated")


def fmt(field: str, value) -> str:
    f = GLOSSARY.get(field)
    if value is None:
        return "n/a (missing)"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if f and f.pct:
        return f"{value * 100:.0f}%"
    if isinstance(value, float):
        return f"{value:,.2f}" if abs(value) < 100 else f"{value:,.0f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def fmt_unit(field: str, value) -> str:
    """Value with its unit, for prose and evidence lines ("2.72 km", "87% of catchment")."""
    f = GLOSSARY.get(field)
    text = fmt(field, value)
    if (not f or value is None or isinstance(value, bool)
            or f.unit in ("", "count", "yes/no", "0-1")):
        return text
    return f"{text} of catchment" if f.pct else f"{text} {f.unit}"


def table_rows(fields: tuple[str, ...], facts: dict) -> list[dict]:
    return [{"Factor": GLOSSARY[k].label, "Value": fmt(k, facts.get(k)),
             "Unit": GLOSSARY[k].unit, "What it means": GLOSSARY[k].meaning}
            for k in fields]


def branch_facts(f: BranchFeatures, d: Decision) -> dict:
    facts = {k: getattr(f, k) for k in BRANCH_TABLE if hasattr(f, k)}
    facts.update(composite=d.composite, **{f"score_{k}": v for k, v in d.scores.items()})
    return {k: round(v, 4) if isinstance(v, float) else v for k, v in facts.items()}


def opportunity_facts(c: CommunityFeatures, o: OpportunityDecision) -> dict:
    facts = {k: getattr(c, k) for k in OPPORTUNITY_TABLE if hasattr(c, k)}
    facts.update(underserved=o.underserved, unsaturated=o.unsaturated)
    return {k: round(v, 4) if isinstance(v, float) else v for k, v in facts.items()}


def _thresholds_note(kind: str) -> str:
    return rubric.THRESHOLDS_WHY if kind == "branch" else opportunity.THRESHOLDS_WHY


def _ev(field: str, facts: dict) -> Evidence:
    return Evidence(field=field, label=GLOSSARY[field].label, value=facts.get(field))


# --- template (no AI) ---------------------------------------------------------------

_BRANCH_EVIDENCE = {
    "demand": ("female_pop_served", "communities_served"),
    "cannibalisation": ("contested_share", "nearest_sibling_km"),
    "competition": ("competitors_per_10k", "competitors_in_catchment"),
    "quality": ("rating", "review_count"),
}


def template_explanation(kind: str, subject_id: str, action: str, facts: dict) -> Explanation:
    if kind == "branch":
        signals = sorted(_BRANCH_EVIDENCE,
                         key=lambda n: abs(facts.get(f"score_{n}", 0.5) - 0.5), reverse=True)[:3]
        reasons = []
        for n in signals:
            s = facts[f"score_{n}"]
            strength = "a strength" if s >= 0.6 else "a weakness" if s <= 0.4 else "neutral"
            main, extra = _BRANCH_EVIDENCE[n]
            reasons.append(Reason(
                claim=f"{GLOSSARY[main].label} is {strength}: {fmt_unit(main, facts.get(main))}.",
                evidence=[_ev(main, facts), _ev(extra, facts), _ev(f"score_{n}", facts)]))
        caption = ("Each signal is scored 0-1 on a fixed scale, where 1 is good for the branch, "
                   "and the composite is their equal-weight average. Demand counts the women "
                   "nearest this branch, cannibalisation counts how many of them a sibling "
                   "branch also competes for, competitive overlap counts rival salons per 10k "
                   "women, and quality is the customer rating.")
    else:
        reasons = [
            Reason(claim=f"Coverage: nearest Bedashing branch is "
                         f"{fmt('nearest_branch_km', facts['nearest_branch_km'])} km away.",
                   evidence=[_ev("nearest_branch_km", facts), _ev("nearest_branch_id", facts),
                             _ev("underserved", facts)]),
            Reason(claim=f"Competition: {fmt('competitors_per_10k', facts['competitors_per_10k'])}"
                         " competitor salons per 10k women.",
                   evidence=[_ev("competitors_per_10k", facts), _ev("competitors", facts),
                             _ev("unsaturated", facts)]),
            Reason(claim=f"Demand: about {fmt('female_pop', facts['female_pop'])} women live here.",
                   evidence=[_ev("female_pop", facts), _ev("hosts_branch", facts)]),
        ]
        caption = ("An area is underserved when the nearest Bedashing branch is far away, and "
                   "unsaturated when it has few rival salons for its population. GROW needs "
                   "both, WATCH has one, and SKIP has neither.")
    return Explanation(subject_id=subject_id, kind=kind, action=action, reasons=reasons,
                       table_caption=caption, thresholds_note=_thresholds_note(kind),
                       source="template")


# --- grounding check ------------------------------------------------------------------

_NUMBER = re.compile(r"(?<![\w.])-?\d[\d,]*\.?\d*")  # "0-1" is a range, not -1


def _allowed_numbers(facts: dict, kind: str) -> list[float]:
    nums = [float(v) for v in facts.values()
            if isinstance(v, (int, float)) and not isinstance(v, bool)]
    nums += [v * 100 for v in nums if 0 <= v <= 1]  # shares and scores quoted as %
    if kind == "branch":
        nums += [rubric.PROTECT_AT, rubric.SHRINK_AT, 4, 0, 1]
        nums += [x for s in rubric.SIGNALS for x in (s.worst, s.best)]
    else:
        nums += [opportunity.FAR_KM, opportunity.UNSATURATED_PER_10K, opportunity.MIN_POP]
    nums += [2, 3, 10, 10_000, 100, 5]  # "3 reasons", "per 10k", "2GIS", "out of 5"
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
    if len(exp.reasons) != 3:
        errors.append(f"expected 3 reasons, got {len(exp.reasons)}")
    allowed = _allowed_numbers(facts, kind)
    for r in exp.reasons:
        if not 2 <= len(r.evidence) <= 3:
            errors.append(f"reason has {len(r.evidence)} data points, expected 2-3")
        for e in r.evidence:
            if e.field not in facts:
                errors.append(f"unknown field {e.field!r}")
            elif not _match(e.value, facts[e.field]):
                errors.append(f"{e.field}: cited {e.value!r}, actual {facts[e.field]!r}")
    for text in [r.claim for r in exp.reasons] + [exp.table_caption]:
        for raw in _NUMBER.findall(text):
            raw = raw.replace(",", "").rstrip(".")
            n = float(raw)
            # Compare at the precision the text uses: "3.1" matches 3.06, "33%" matches 33.4.
            places = len(raw.split(".")[1]) if "." in raw else 0
            if not any(_close(n, a) or round(a, places) == n for a in allowed):
                errors.append(f"number {raw} in text not in fact sheet")
    return errors


# --- LLM --------------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You explain retail network decisions for Bedashing Beauty Lounge's portfolio team, who "
    "will defend them to the COO and a private-equity board. The decision is already made by "
    "a rule-based model; you explain it, you never change it. Use only the fact sheet. Every "
    "number you write must appear in the fact sheet or the thresholds. Write like a board "
    "memo: short, concrete claims. Never mention revenue, rent or profit figures (none exist). "
    "Always answer by calling the submit_explanation tool."
)
# Server-side refusal fallback: a declined request is re-run on Anthropic's recommended
# substitute model inside the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

# strict: the API guarantees inputs match this schema. Strict mode doesn't support array
# length limits, so "exactly 3 reasons, 2-3 data points" is enforced by verify() instead.
EXPLAIN_TOOL = {
    "name": "submit_explanation",
    "strict": True,
    "description": "Explain the decision: exactly 3 reasons, each backed by 2-3 data points "
                   "copied from the fact sheet, plus a caption for the factor table.",
    "input_schema": {
        "type": "object",
        "properties": {
            "reasons": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
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
                    "required": ["claim", "evidence"],
                    "additionalProperties": False,
                },
            },
            "table_caption": {
                "type": "string",
                "description": "2-3 sentences explaining, for a non-technical executive, what "
                               "the factors in the table measure and how to read them for "
                               "this specific branch or area.",
            },
        },
        "required": ["reasons", "table_caption"],
        "additionalProperties": False,
    },
}


def _user_message(kind: str, subject_id: str, action: str, facts: dict, errors: list[str]) -> str:
    table = BRANCH_TABLE if kind == "branch" else OPPORTUNITY_TABLE
    msg = {
        "subject": f"{kind} {subject_id}",
        "decision": action,
        "fact_sheet": facts,
        "field_glossary": {k: {"label": GLOSSARY[k].label, "unit": GLOSSARY[k].unit,
                               "meaning": GLOSSARY[k].meaning} for k in table},
        "thresholds": _thresholds_note(kind),
    }
    if errors:
        msg["your_previous_attempt_failed_checks"] = errors
    return json.dumps(msg)


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
            raw = tool_use.input
            exp = Explanation(
                subject_id=subject_id, kind=kind, action=action,
                reasons=[Reason(claim=r["claim"],
                                evidence=[Evidence(field=e["field"],
                                                   label=GLOSSARY.get(e["field"], Field(
                                                       e["field"], "", "")).label,
                                                   value=e.get("value"))
                                          for e in r["evidence"]])
                         for r in raw["reasons"]],
                table_caption=raw["table_caption"], thresholds_note=_thresholds_note(kind),
                source="ai")
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
    data = load_baseline(settings)
    # Reuse entries whose exact facts are unchanged, so a re-run only fills gaps (failed
    # or changed subjects). Entries for subjects that no longer match are dropped below.
    cache = load_cache()
    subjects = [("branch", f.branch_id, data.decision_for(f.branch_id).action,
                 branch_facts(f, data.decision_for(f.branch_id))) for f in data.features]
    opp = {o.community_id: o for o in data.opportunities}
    subjects += [("opportunity", c.community_id, opp[c.community_id].action,
                  opportunity_facts(c, opp[c.community_id])) for c in data.community_features]
    ai = 0
    for kind, sid, action, facts in subjects:
        ai += explain(kind, sid, action, facts, cache=cache, client=client).source == "ai"
    current = {cache_key(*subject) for subject in subjects}
    cache = {k: v for k, v in cache.items() if k in current}
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False, sort_keys=True))
    print(f"explain: {ai}/{len(subjects)} AI explanations passed grounding; "
          f"{len(subjects) - ai} fall back to template. Wrote {CACHE_PATH}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
