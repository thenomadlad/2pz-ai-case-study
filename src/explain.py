"""Pyramid explanations: an answer (headline), 2-5 supporting arguments, 2-5 data points each.

Three kinds: a `lounge` call, a growth-`area` call and the `uae` network summary. The scorecard /
growth tests make every decision, and `prioritize` decides which arguments matter and in what
order: importance is computed, never left to the AI. An LLM then writes the pyramid from a fact
sheet. Every cited {field, value} and every number in its prose must match that fact sheet, and
the arguments must be exactly the ranked topics (`verify`), or it is regenerated once and then
replaced by the deterministic template. Explanations are cached by a hash of their fact sheet in
a committed file, so the public deploy shows AI output without an API key, and a stale entry can
never be served for changed numbers.

Two ways to fill the cache for the baseline (both skip NOT SCORED lounges and SKIP areas):
- `uv run python -m src.explain` (just explain): the Anthropic API, needs ANTHROPIC_API_KEY.
- Offline: `... src.explain prompts DIR` writes one prompt per missing subject; write the answers
  (e.g. in a Claude Code session) to DIR/answers/; `... src.explain check DIR` verifies them;
  `... src.explain ingest DIR` verifies and caches the grounded ones.
"""
import hashlib
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass

from src.config import REPO_ROOT, settings
from src.model import growth, scorecard
from src.models import (
    Area,
    AreaDecision,
    Decision,
    Evidence,
    Explanation,
    LoungeFeatures,
    Reason,
)

logger = logging.getLogger(__name__)

CACHE_PATH = REPO_ROOT / "data" / "explanations" / "cache.json"
PROMPT_VERSION = "v7"


MIN_ITEMS, MAX_ITEMS = 2, 5  # per pyramid level: enough to support, few enough to read


@dataclass(frozen=True)
class Field:
    label: str
    unit: str
    meaning: str
    pct: bool = False  # stored as 0-1, shown as %


LIMIT_WITHIN_EMIRATE = (
    "Keep or shrink is judged within the site's emirate, but a growth area needs an absolute "
    f"{growth.NEW_SITE_MIN:,} net new women, so a PROTECT site can fail the growth test as a new opening: nad-al-sheba is PROTECT (it "
    "out-serves 68% of Dubai salon sites), yet a typical lounge there would serve about 2,700 women "
    "(baseline 2026-10-11).")
GLOSSARY: dict[str, Field] = {
    # --- lounge ---
    "catchment_women": Field(
        "Women 15+ in catchment", "women",
        "Women aged 15+ living in the ~2 km cells within a 15-min drive (typical midday traffic). "
        "WorldPop adults, rebalanced so worker housing counts few women. Raw: not affluence-weighted."),
    "addressable_women": Field(
        "Addressable women 15+", "women",
        "Catchment women times an affluence weight (observed median rent vs the women-weighted "
        "median, to the affluence elasticity; mean weight 1). Affluence is off at baseline "
        "(elasticity 0), so this equals the raw count; it moves only in the assumption what-ifs. "
        "Dubai rents only; elsewhere neutral (weight 1)."),
    "affluence_rent": Field(
        "Affluence rent", "AED/yr",
        "Median annual household rent (DLD Ejari contracts, Jul-Oct 2026), weighted by women, over "
        "the cells with an observed rent. Dubai rents only; elsewhere neutral, so n/a."),
    "affluence_coverage": Field(
        "Affluence coverage", "% of women",
        "Share of the women here living in cells with an observed rent. The rest are weighted "
        "neutral: affluence unknown. Dubai rents only; elsewhere neutral.", pct=True),
    "catchment_cells": Field("Cells in catchment", "count",
                             "Populated ~2 km grid cells whose centre is within the drive time."),
    "shared_share": Field(
        "Shared catchment", "% of catchment women",
        "Share of the catchment's women who live in cells another open Bedashing lounge also "
        "reaches: the cannibalisation measure.", pct=True),
    "premium_pool": Field(
        "Premium salons in catchment", "count",
        "Google Places salons in the catchment that count as premium: Google price "
        "'expensive' or above, or (unpriced) at least the median reviews and rated 4.3+."),
    "substitutes_k": Field(
        "Premium substitutes", "count",
        "The most-reviewed premium salons that together hold 60% of the catchment's premium "
        "reviews: the lounge's real competition."),
    "capture": Field(
        "Capture", "% of reviews",
        "Lounge reviews ÷ (lounge + substitutes' reviews, scaled up for salons the search "
        "missed). A proxy for share of premium customers.", pct=True),
    "thin_premium_market": Field(
        "Thin premium market", "yes/no",
        f"Fewer than {scorecard.THIN_MARKET} premium salons: capture of a tiny pool is noisy. "
        "Capture is shown, not scored."),
    "lounge_rating": Field("Google rating", "stars (of 5)", "The lounge's Google rating."),
    "lounge_reviews": Field("Google reviews", "count", "Reviews behind the lounge's rating."),
    "substitutes_median_rating": Field("Premium salons' median rating", "stars (of 5)",
                                       "Median Google rating of the premium salons in the catchment with 20+ reviews."),
    "rating_gap": Field("Rating gap", "stars",
                        "Lounge rating minus the median rating of the premium salons in its catchment (20+ reviews)."),
    "level_flips": Field(
        "Assumption sensitivity", f"of {scorecard.COMBOS} combinations",
        f"In how many of the {scorecard.COMBOS} combinations of drive time, competitor coverage and "
        "worker-housing share (low, medium, high each) this lounge's call changes. Affluence weighting "
        "is off, so it isn't varied."),
    "composite": Field(
        "Composite score", "0-1",
        "Weighted average of the signal scores below (weights in the Threshold column). "
        f"PROTECT ≥ {scorecard.PROTECT_AT}, SHRINK ≤ {scorecard.SHRINK_AT}. "
        + LIMIT_WITHIN_EMIRATE),
    **{f"score_{s.name}": Field(
        f"{s.name.capitalize()} score", "0-1",
        f"{s.label}, converted to a fixed 0-1 score where 1 is best for the lounge "
        "(scale in the Threshold column).")
       for s in scorecard.SIGNALS},
    **{f"contrib_{s.name}": Field(
        f"{s.name.capitalize()} contribution", "0-1",
        f"What the {s.name} score adds to the composite: weight × score ÷ total weight. The "
        f"{len(scorecard.SIGNALS)} contributions sum to the composite.")
       for s in scorecard.SIGNALS},
    "next_call": Field("Nearest other call", "",
                       "The call this lounge would get if its composite crossed the nearest line."),
    "line_gap": Field("Distance to that line", "0-1",
                      "How far the composite would have to move to reach the nearest other call."),
    "flip_driver": Field("Driver that could flip it", "",
                         "The highest-ranked location or market signal that, moving alone, could "
                         "carry the composite across that line (rating is left out: it is not a "
                         "portfolio lever). n/a when none can."),
    "flip_value": Field("Value that flips it", "",
                        "The value of that driver's input (in its own unit) at which the call "
                        "changes, all else equal."),
    # --- growth area ---
    "area_name": Field("Area", "", "OpenStreetMap place name nearest the area's cells."),
    "emirate": Field("Emirate", "", "Emirate the area or lounge lies in."),
    "women": Field("Women 15+", "women", "Women aged 15+ living in the area's cells (raw)."),
    "cells": Field("Cells", "count", "Populated ~2 km cells in the area (every unreached cell with this OSM place name)."),
    "worker_share": Field("Worker housing", "% of adults",
                          "Share of the area's adults living in worker housing (OSM industrial "
                          "land use).", pct=True),
    "premium_salons": Field("Premium salons", "count",
                            "Premium salons found in the area's searched cells."),
    "site_served": Field("Women a typical lounge would serve here", "women",
                         "What-if: the women a typical lounge (frozen at 757 reviews, 4.6★) would serve at this site, "
                         "with this lounge closed and its siblings and rivals open (Huff). The demand signal: it "
                         "scores the site, not how much the lounge itself sells."),
    "served_women": Field("Women served (Huff)", "women",
                          "Model estimate of the customers behind the services this lounge sells: its Huff share of "
                          "every cell it reaches within 20 min. It rests on the lounge's own reviews (our proxy for "
                          "services sold) and rating, so it is context, not scored."),
    "performance_vs_site": Field("Performance vs site", "x its site",
                                 "Women this lounge serves ÷ women a typical lounge would serve at its site. Read as "
                                 "'The model estimates this lounge is performing 2.7x compared to its site'. Context, "
                                 "not scored: above 1x the lounge sells more than a typical lounge would at its site (from its "
                                 "reviews and rating), not the site."),
    "absorbed_share": Field("Absorbed by siblings", "% of served", "Share of its served women other lounges take over if it closes.", pct=True),
    "site_cost_k": Field("Site cost", "AED 1k/yr", "Shop rent x 150 m² (assumed unit) + fit-out of AED 3,000/m² over 5 years (assumed)."),
    "demand_ref": Field("Demand ranked among", "", "Whose salon sites the demand percentile ranks against: the site's emirate, or UAE when the emirate has under 50 reference salon sites."),
    "demand_pct": Field("Site demand percentile", "% of salon sites",
                        "Share of the reference salon sites in its emirate (UAE-wide under 50) that a typical lounge "
                        "would out-serve at this site: the women it would serve there (for an area, a new lounge) "
                        "against what it would serve at each competitor salon site, frozen 2026-10-11.", pct=True),
    "demand_pct_uae": Field("Demand percentile UAE-wide", "% of UAE salon sites",
                            "The same, against all 1,123 UAE reference salon sites. Context, not scored.", pct=True),
    "rent_ratio": Field("Rent ratio", "",
                        "Median shop rent at the reference salon sites in its emirate ÷ this site's shop rent: above 1 "
                        "is cheaper than a typical salon site there. Rent only, no served women."),
    "rent_fallback": Field("Rent is the emirate median", "yes/no",
                           "Yes: the shop rent here is its emirate's median standing in for cells with no DLD, ADREC "
                           "or listings rent (an area: half or more of its women), not an observation of the place. "
                           "The rent test is neutral (passes; a lounge's rent scores 0.5) and the call is low confidence."),
    "rent_pct_uae": Field("Rent percentile UAE-wide", "% of UAE salon sites",
                          "Share of the UAE reference salon sites with a lower shop rent (higher = more expensive). Context, not scored.",
                          pct=True),
    "new_site_served": Field("New lounge would serve", "women", "What-if: women a typical new lounge here would serve (Huff)."),
    "new_site_taken": Field("Taken from our lounges", "women", "What-if: of those, women it would take from our existing lounges."),
    "new_site_net": Field("Net new women", "women", "What-if: women a new lounge here adds to the network (served − taken)."),
    "unserved_women": Field("Unserved women", "women", "Addressable women no premium salon serves today (Huff)."),
    "site_rent_m2": Field("Shop rent at the site", "AED/m²/yr",
                          "Commercial (shop) rent where the lounge sits: our cost, not customer affluence. "
                          "Dubai: the median of DLD Ejari shop contracts in its area; Abu Dhabi: ADREC's 2025 "
                          "street-retail rate for its district; northern emirates: median asking rent of nearby "
                          "shop listings; else the emirate median. An area rate that mixes mall and street shops, "
                          "not the lounge's lease: a mall site can be well above it."),
    "women_per_rent_k": Field("Women per AED 1k of rent", "women",
                              "Addressable women per AED 1,000 of annual rent for a 150 m² unit (assumed): "
                              "the unit size sets the level, never the ranking. Display only, not scored."),
    "shop_rent_m2": Field("Shop rent in the area", "AED/m²/yr",
                          "Women-weighted median shop rent over the area's cells (DLD in Dubai, ADREC in Abu Dhabi, "
                          "listings in the northern emirates, else the emirate median). Mixes mall and street shops."),
    "premium_reviews_per_1k": Field(
        "Premium saturation", "reviews per 1k women",
        "Premium salons' Google reviews (scaled up for missed salons) per 1,000 women in the "
        "searched cells: the same measure for a lounge's catchment and a growth area. Scored "
        "lounge catchments with 10+ premium salons run 88-630; empty areas under 10. Lounges: "
        "shown, not scored."),
    "data_coverage": Field("Competitor data coverage", "% of women",
                           "Share of the area's women in cells our salon search covered.",
                           pct=True),
    "nearest_lounge_id": Field("Nearest lounge", "", "Closest open, scored Bedashing lounge."),
    "confidence": Field(
        "Confidence", "",
        f"Low within {growth.NEAR_LINE:.0%} of the net-new-women line or with under "
        f"{growth.MIN_COVERAGE:.0%} of the women searched; high {growth.FAR_LINE:.0%}+ from the line; "
        "else medium."),
    "nearest_lounge_km": Field("Distance to nearest lounge", "km",
                               "Straight-line distance to the closest open, scored lounge (an area can sit inside a lounge's catchment: the what-if counts what a new lounge would take from it)."),
    "big_enough": Field("Big enough", "yes/no",
                        f"A new lounge here would add at least {growth.NEW_SITE_MIN:,} net new women and "
                        f"worker housing is under {growth.WORKER_CAP:.0%} of adults."),
    "unsaturated": Field("Unsaturated", "yes/no",
                         f"Fewer than {growth.UNSATURATED_PER_1K:g} premium reviews per 1k women "
                         "(n/a when too little of the area was searched). Context only: competition "
                         "already shapes the net new women, so it is not a separate test."),
    "new_site_min": Field("Size line", "net new women",
                          "Net new women a new lounge must add to the network: about what our median "
                          "lounge serves today."),
    "skip_under_women": Field("Size floor", "women", "Under this the area is skipped."),
    "unsaturated_per_1k": Field("Saturation line", "reviews per 1k women",
                                "Under this the area is unsaturated (context, not a test)."),
    "worker_cap": Field("Worker-housing cap", "% of adults",
                        "Above this the women estimate is too uncertain to GROW.", pct=True),
    "min_coverage": Field("Coverage needed", "% of women",
                          "Less competitor data than this makes the call low confidence (unsearched cells are imputed).", pct=True),
    "size_gap": Field("Size gap", "net new women",
                      "Net new women minus the size line: positive is headroom above it, "
                      "negative is how many more a new lounge would need to add."),
    "saturation_gap": Field("Saturation gap", "reviews per 1k women",
                            "Saturation line minus premium saturation: positive is room under the "
                            "line, negative is how far over it. Context only. n/a when unsearched."),
    "rent_gap": Field("Rent gap", "",
                      "Rent ratio minus 1 (the median salon site in its emirate): GROW needs 0 or more, "
                      "else a big-enough area is WATCH. n/a when no shop rent is known."),
    "demand_gap": Field("Demand gap", "% of salon sites",
                        f"Site demand percentile minus {growth.DEMAND_PCT_MIN:.0%}: GROW needs 0 or more, else a "
                        "big-enough area is WATCH.", pct=True),
    "worker_gap": Field("Worker-housing gap", "% of adults",
                        "Worker-housing cap minus worker share: negative means over the cap.",
                        pct=True),
    "coverage_gap": Field("Coverage gap", "% of women",
                          "Competitor data coverage minus the coverage needed: negative means "
                          "too little was searched to GROW.", pct=True),
    # --- uae (network summary: the Executive Summary in one paragraph) ---
    "lounges_scored": Field("Lounges scored", "count", "UAE lounges given a call."),
    "hold_count": Field("HOLD", "lounges", "Lounges between the two thresholds."),
    "low_confidence_count": Field(
        "Low-confidence calls", "lounges",
        "Lounge calls within 0.05 of a threshold, on the emirate-median fallback rent, or that flip "
        "in 9+ of the 27 assumption combinations or when a signal weight moves ±25%."),
    "near_line_count": Field("Calls near a line", "lounges",
                             "Lounge composites within 0.05 of the PROTECT or SHRINK line."),
    "shrink_count": Field("SHRINK", "lounges", f"Lounges with composite ≤ {scorecard.SHRINK_AT}, any confidence."),
    "shrink_high_count": Field("SHRINK, high confidence", "lounges", "SHRINK lounges with a high-confidence call."),
    "shrink_high_lounges": Field("SHRINK lounges, high confidence", "", "Ids of high-confidence SHRINK lounges."),
    "protect_count": Field("PROTECT", "lounges", f"Lounges with composite ≥ {scorecard.PROTECT_AT}, any confidence."),
    "protect_high_count": Field("PROTECT, high confidence", "lounges", "PROTECT lounges with a high-confidence call."),
    "protect_high_lounges": Field("PROTECT lounges, high confidence", "", "Ids of high-confidence PROTECT lounges."),
    "grow_count": Field("GROW", "areas", "Areas passing every growth test, any confidence."),
    "grow_high_count": Field("GROW, high confidence", "areas", "GROW areas with a high-confidence call."),
    "grow_high_lead_emirates": Field("Where most high-confidence GROW areas are", "",
                                     "The one or two emirates holding the most high-confidence GROW areas."),
    "grow_high_lead_count": Field("High-confidence GROW areas in those emirates", "areas",
                                  "How many of the high-confidence GROW areas lie in the leading emirates."),
    "new_site_min_share": Field("GROW size line, as a share of our served market", "%",
                                "The size line over the women our lounges serve today (model estimate).",
                                pct=True),
    "revenue_data_available": Field("Revenue data", "yes/no", "Per-lounge revenue, margin or bookings."),
    "lease_data_available": Field("Lease data", "yes/no", "Per-lounge lease terms or rent actually paid. "
                                  "The model scores area shop rent per m², not the lease."),
}

# Each argument a pyramid can make, with the facts that can back it. `prioritize` picks
# which apply and orders them; every reason must cite at least one of its topic's fields.
TOPICS: dict[str, dict[str, tuple[str, ...]]] = {
    "lounge": {
        "demand": ("demand_pct", "demand_pct_uae", "demand_ref", "site_served", "served_women", "performance_vs_site", "score_demand", "addressable_women",
                   "catchment_women", "affluence_coverage", "affluence_rent", "catchment_cells", "contrib_demand"),
        "cannibalisation": ("absorbed_share", "shared_share"),
        "cost": ("rent_ratio", "rent_fallback", "rent_pct_uae", "site_rent_m2", "site_cost_k", "score_cost", "contrib_cost"),
        "capture": ("capture", "substitutes_k", "premium_pool", "thin_premium_market"),
        "rating": ("rating_gap", "lounge_rating", "substitutes_median_rating", "lounge_reviews"),
    },
    "area": {
        "size": ("new_site_net", "new_site_served", "new_site_taken", "new_site_min", "size_gap",
                 "big_enough", "women", "skip_under_women", "unserved_women"),
        "demand": ("demand_pct", "demand_gap", "demand_pct_uae", "demand_ref", "new_site_served"),
        "cost": ("rent_ratio", "rent_fallback", "rent_gap", "rent_pct_uae", "shop_rent_m2", "site_cost_k"),
        "saturation": ("premium_reviews_per_1k", "premium_salons", "unsaturated",
                       "unsaturated_per_1k", "saturation_gap"),
        "reach": ("nearest_lounge_km", "nearest_lounge_id"),
        "worker_housing": ("worker_share", "worker_cap", "worker_gap"),
        "data_gap": ("data_coverage", "min_coverage", "unsaturated", "coverage_gap"),
    },
    "uae": {   # the Executive Summary's order: review, protect, grow, then how sure
        "shrink": ("shrink_high_count", "shrink_high_lounges", "shrink_count"),
        "protect": ("protect_high_count", "protect_high_lounges", "protect_count"),
        "grow": ("grow_high_count", "grow_high_lead_emirates", "grow_high_lead_count", "grow_count",
                 "new_site_min", "new_site_min_share"),
        "confidence": ("low_confidence_count", "lounges_scored", "near_line_count", "hold_count",
                       "revenue_data_available", "lease_data_available"),
    },
}
TOPIC_LABELS = {
    "demand": "Site demand", "cannibalisation": "Cannibalisation", "cost": "Site rent", "capture": "Capture",
    "rating": "Rating vs rivals", "size": "Net new women", "saturation": "Competition",
    "reach": "Distance to a lounge", "worker_housing": "Demand reliability",
    "data_gap": "What we couldn't search", "shrink": "What to review",
    "grow": "Where to search for sites", "protect": "What to defend", "confidence": "How sure we are",
}
IMPORTANT = 0.1  # a lounge signal must sit this far from neutral (0.5), weighted, to be an argument


KNIFE_EDGE = 0.01   # within this of a line, show a composite to 3 decimals (al-maqta: 0.353 vs 0.35)


def composite_digits(line_gap: float) -> int:
    return 3 if abs(line_gap) < KNIFE_EDGE else 2


def fmt(field: str, value, pct_digits: int = 0) -> str:
    f = GLOSSARY.get(field)
    if value is None:
        return "n/a (missing)"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if f and f.pct:
        return f"{value * 100:.{pct_digits}f}%"
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
    return text + f.unit[1:] if f.pct else f"{text} {f.unit}"


def _scale(signal) -> str:
    return (f"{signal.name.capitalize()} score: {fmt_unit(signal.field, signal.worst)} → 0, "
            f"{fmt_unit(signal.field, signal.best)} → 1")


# The decision rule each factor feeds, built from the model's own constants.
_TOTAL_WEIGHT = sum(s.weight for s in scorecard.SIGNALS)
THRESHOLDS: dict[str, str] = {
    **{s.field: f"{_scale(s)}; weight {s.weight:g}" for s in scorecard.SIGNALS},
    **{f"score_{s.name}": f"Weight {s.weight:g} of {_TOTAL_WEIGHT:g}" for s in scorecard.SIGNALS},
    "composite": (f"PROTECT ≥ {scorecard.PROTECT_AT} · HOLD between · "
                  f"SHRINK ≤ {scorecard.SHRINK_AT}"),
    "thin_premium_market": "Context: capture is shown, not scored",
    "level_flips": f"Low confidence at {scorecard.FLIP_LOW} or more of {scorecard.COMBOS}",
    "new_site_net": f"GROW needs {growth.NEW_SITE_MIN:,}; WATCH from {growth.NEW_SITE_MIN // 2:,}",
    "women": f"SKIP under {growth.SKIP_UNDER_WOMEN:,}",
    "affluence_coverage": "Under 50%: affluence mostly unknown, weighted neutral",
    "worker_share": f"GROW needs under {growth.WORKER_CAP:.0%}",
    "premium_reviews_per_1k": f"Unsaturated under {growth.UNSATURATED_PER_1K:g} (context, not a test)",
    "data_coverage": f"GROW needs {growth.MIN_COVERAGE:.0%}",
    "big_enough": (f"GROW needs big enough, rent ratio {growth.RENT_RATIO_MIN:g} or more (or unknown) and demand "
                   f"percentile {growth.DEMAND_PCT_MIN:.0%} or more"),
    "unsaturated": "Context, not a test",
    **{f"contrib_{s.name}": f"Sums to the composite (max {s.weight / _TOTAL_WEIGHT:.2f})"
       for s in scorecard.SIGNALS},
    "size_gap": f"GROW needs 0 or more (line {growth.NEW_SITE_MIN:,})",
    "saturation_gap": f"Context, not a test (line {growth.UNSATURATED_PER_1K:g})",
    "rent_gap": "GROW needs 0 or more (or no rent known, or the emirate-median fallback)",
    "rent_fallback": "Yes: rent test neutral, low confidence",
    "demand_gap": "GROW needs 0 or more",
    "worker_gap": f"GROW needs above 0 (cap {growth.WORKER_CAP:.0%})",
    "coverage_gap": f"Under 0: low confidence (needs {growth.MIN_COVERAGE:.0%})",
}


def _in_unit(field: str, value, pct_digits: int = 0) -> str:
    """A signal input with its full unit ("38,123 women", "47% of catchment women")."""
    f, text = GLOSSARY[field], fmt(field, value, pct_digits)
    return text + (f.unit[1:] if f.pct else f" {f.unit}" if f.unit else "")


def _flip_text(facts: dict, pct_digits: int = 0) -> str:
    """flip_value in its driver's own unit."""
    sig = next(s for s in scorecard.SIGNALS if s.name == facts["flip_driver"])
    return _in_unit(sig.field, facts["flip_value"], pct_digits)


def what_would_change(kind: str, facts: dict) -> list[str]:
    """The distance to each line that matters, in words (E3): the nearest other call and the value
    that would flip a lounge; for an area, the gap to each test."""
    if kind == "lounge":
        if "next_call" not in facts:
            return []
        nd = composite_digits(facts["line_gap"])
        out = [(f"Composite {facts['composite']:.{nd}f} is {facts['line_gap']:.{nd}f} from the "
                f"{facts['next_call']} line.")]
        if facts["flip_driver"]:
            sig = next(s for s in scorecard.SIGNALS if s.name == facts["flip_driver"])
            flip, now = _flip_text(facts), _in_unit(sig.field, facts[sig.field])
            if flip == now:   # a knife edge: one more decimal tells them apart
                flip, now = _flip_text(facts, 1), _in_unit(sig.field, facts[sig.field], 1)
            out.append(f"On its own, {GLOSSARY[sig.field].label.lower()} would have to reach "
                       f"{flip} (now {now}) to make it {facts['next_call']}.")
        else:
            out.append("No single market signal could move it there on its own.")
        return out
    if kind != "area":
        return []
    gap = facts["size_gap"]
    out = [f"Size: {fmt('size_gap', abs(gap))} net new women "
           + ("above the line." if gap >= 0 else "short of the line.")]
    dem = facts.get("demand_gap")
    if dem is not None:
        out.append(f"Demand: {fmt('demand_pct', facts['demand_pct'])} of {facts['demand_ref']} salon sites out-served, "
                   f"{fmt('demand_gap', abs(dem))} " + ("above the line." if dem >= 0 else "short of the line."))
    rent = facts.get("rent_gap")
    if facts.get("rent_fallback"):
        out.append(f"Rent: the {facts['emirate']} median stands in (not observed), so the rent test is neutral.")
    elif rent is not None:
        out.append(f"Rent: ratio {fmt('rent_ratio', facts['rent_ratio'])} against its emirate's median salon site, "
                   f"{fmt('rent_gap', abs(rent))} " + ("above the 1 line." if rent >= 0 else "short of the 1 line."))
    if facts["worker_gap"] <= 0:
        out.append(f"Worker housing: {fmt('worker_gap', -facts['worker_gap'])} of adults over the cap.")
    if facts["coverage_gap"] < 0:
        out.append(f"Search coverage: {fmt('coverage_gap', -facts['coverage_gap'])} of women short "
                   "of what a confident call needs.")
    return out


def table_rows(fields: tuple[str, ...], facts: dict) -> list[dict]:
    return [{"Factor": GLOSSARY[k].label,
             "Value": _flip_text(facts) if k == "flip_value" and facts.get("flip_driver")
             else fmt(k, facts.get(k)),
             "Unit": GLOSSARY[k].unit, "Threshold": THRESHOLDS.get(k, "—"),
             "What it means": GLOSSARY[k].meaning}
            for k in fields]


def _rounded(facts: dict) -> dict:
    return {k: round(v, 4) if isinstance(v, float) else v for k, v in facts.items()}


# --- facts ------------------------------------------------------------------------------

LOUNGE_TABLE = ("demand_pct", "demand_ref", "demand_pct_uae", "site_served", "served_women", "performance_vs_site", "absorbed_share", "catchment_women", "addressable_women", "affluence_rent", "affluence_coverage",
                "catchment_cells", "shared_share", "premium_pool", "premium_reviews_per_1k",
                "rent_ratio", "rent_pct_uae", "site_rent_m2", "women_per_rent_k",
                "substitutes_k", "capture", "thin_premium_market",
                "lounge_rating", "lounge_reviews", "substitutes_median_rating", "rating_gap",
                "level_flips", "composite", "score_demand", "score_cost", "site_cost_k",
                "contrib_demand", "contrib_cost", "next_call", "line_gap", "flip_driver",
                "flip_value")
AREA_TABLE = ("women", "addressable_women", "affluence_rent", "affluence_coverage", "cells", "worker_share", "premium_salons", "premium_reviews_per_1k",
              "shop_rent_m2", "women_per_rent_k", "new_site_served", "new_site_taken", "new_site_net",
              "unserved_women", "demand_pct", "demand_ref", "demand_pct_uae", "rent_ratio", "rent_pct_uae", "site_cost_k", "data_coverage", "nearest_lounge_id", "nearest_lounge_km", "big_enough",
              "unsaturated", "confidence", "size_gap", "demand_gap", "rent_gap", "saturation_gap", "worker_gap", "coverage_gap")
NOT_SCORED_ACTION = "NOT SCORED"


def lounge_facts(f: LoungeFeatures, d: Decision, flips: int | None = None) -> dict:
    facts = {k: getattr(f, k) for k in LOUNGE_TABLE if hasattr(f, k)}
    facts.update(lounge_rating=f.rating, lounge_reviews=f.review_count, level_flips=flips,
                 composite=d.composite, **{f"score_{k}": v for k, v in d.scores.items()})
    if growth.rent_fallback(f):   # only when true: unaffected fact sheets keep their cache keys
        facts.update(rent_fallback=True, emirate=f.emirate)
    if d.action != NOT_SCORED_ACTION:
        facts.update(_counterfactual(facts, d.action))
    return _rounded(facts)


def _counterfactual(facts: dict, action: str) -> dict:
    """Each signal's share of the composite, the nearest other call and how far away it is, and the
    value of the top-ranked market signal that would flip the call on its own (E3). Derived from
    the scorecard's own weights and anchors; changes no call."""
    c, w = facts["composite"], {s.name: s.weight for s in scorecard.SIGNALS}
    out = {f"contrib_{n}": w[n] * facts[f"score_{n}"] / _TOTAL_WEIGHT for n in w}
    up, down = scorecard.PROTECT_AT - c, c - scorecard.SHRINK_AT
    nxt, gap, sign = {"PROTECT": ("HOLD", -up, -1), "SHRINK": ("HOLD", -down, 1)}.get(
        action, ("PROTECT", up, 1) if up <= down else ("SHRINK", down, -1))
    out.update(next_call=nxt, line_gap=gap, flip_driver=None, flip_value=None)
    for topic in prioritize("lounge", facts, action) + [s.name for s in scorecard.SIGNALS]:
        s = next(s for s in scorecard.SIGNALS if s.name == topic)
        if topic == "rating" or (topic == "capture" and facts.get("thin_premium_market")) \
                or (topic == "cost" and facts.get("rent_fallback")):   # fallback rent scores neutral whatever its ratio
            continue  # rating is not a portfolio lever (OB4); thin-market capture is damped toward neutral, off its scale
        needed = facts[f"score_{topic}"] + sign * gap * _TOTAL_WEIGHT / s.weight
        if 0 <= needed <= 1:
            out.update(flip_driver=topic, flip_value=s.worst + needed * (s.best - s.worst))
            break
    return out


def area_facts(a: Area, d: AreaDecision) -> dict:
    facts = {k: getattr(a, k) for k in AREA_TABLE if hasattr(a, k)}
    facts.update(area_name=a.name, emirate=a.emirate, big_enough=d.big_enough,
                 unsaturated=d.unsaturated, confidence=d.confidence, new_site_min=growth.NEW_SITE_MIN,
                 skip_under_women=growth.SKIP_UNDER_WOMEN,
                 unsaturated_per_1k=growth.UNSATURATED_PER_1K, worker_cap=growth.WORKER_CAP,
                 min_coverage=growth.MIN_COVERAGE,
                 # Gap to each test's line (E3): positive passes, negative is the shortfall.
                 size_gap=round((a.new_site_net or 0.0) - growth.NEW_SITE_MIN),
                 demand_gap=None if a.demand_pct is None else a.demand_pct - growth.DEMAND_PCT_MIN,
                 rent_gap=None if a.rent_ratio is None or growth.rent_fallback(a) else a.rent_ratio - growth.RENT_RATIO_MIN,
                 saturation_gap=None if a.premium_reviews_per_1k is None
                 else growth.UNSATURATED_PER_1K - a.premium_reviews_per_1k,
                 worker_gap=growth.WORKER_CAP - a.worker_share,
                 coverage_gap=a.data_coverage - growth.MIN_COVERAGE)
    if growth.rent_fallback(a):   # only when true: unaffected fact sheets keep their cache keys
        facts["rent_fallback"] = True
    return _rounded(facts)


def uae_facts(r) -> dict:
    """The network summary's facts, counted as the Executive Summary counts them: high-confidence calls
    first, every call second. No sum over growth areas: each is a separate what-if, so they overlap."""
    scored = [d for d in r.decisions if d.action != NOT_SCORED_ACTION]
    high = lambda ds, a: [d for d in ds if d.action == a and d.confidence == "high"]
    count = lambda ds, a: sum(d.action == a for d in ds)
    emirate = {a.area_id: a.emirate for a in r.areas}
    grow_high = high(r.area_decisions, "GROW")
    lead = Counter(emirate[d.area_id] for d in grow_high).most_common(2)
    served = sum(f.served_women or 0 for f in r.features)
    return _rounded({
        "lounges_scored": len(scored),
        "hold_count": count(scored, "HOLD"),
        "low_confidence_count": sum(d.confidence == "low" for d in scored),
        "near_line_count": sum(min(abs(d.composite - scorecard.PROTECT_AT), abs(d.composite - scorecard.SHRINK_AT))
                               < scorecard.LOW_MARGIN for d in scored),
        "shrink_count": count(scored, "SHRINK"),
        "shrink_high_count": len(high(scored, "SHRINK")),
        "shrink_high_lounges": ", ".join(sorted(d.branch_id for d in high(scored, "SHRINK"))) or "none",
        "protect_count": count(scored, "PROTECT"),
        "protect_high_count": len(high(scored, "PROTECT")),
        "protect_high_lounges": ", ".join(sorted(d.branch_id for d in high(scored, "PROTECT"))) or "none",
        "grow_count": count(r.area_decisions, "GROW"),
        "grow_high_count": len(grow_high),
        "grow_high_lead_emirates": " and ".join(e for e, _ in lead) or "none",
        "grow_high_lead_count": sum(n for _, n in lead),
        "new_site_min": growth.NEW_SITE_MIN,
        "new_site_min_share": growth.NEW_SITE_MIN / served if served else None,
        "revenue_data_available": False,
        "lease_data_available": False,
    })


# --- prioritization: which arguments, in what order --------------------------------------

def prioritize(kind: str, facts: dict, action: str) -> list[str]:
    """The 2-5 arguments that matter most for this decision, most important first."""
    if kind == "lounge":
        if action == NOT_SCORED_ACTION:
            return ["demand", "capture"]
        # Importance = how far a weighted signal sits from neutral, in the direction of the call:
        # strengths for PROTECT, weaknesses for SHRINK, either for HOLD.
        sign = {"PROTECT": 1, "SHRINK": -1}.get(action)
        w = {s.name: s.weight for s in scorecard.SIGNALS}

        def lweight(topic: str) -> float:
            delta = (facts[f"score_{topic}"] - 0.5) * w[topic]
            return delta * sign if sign else abs(delta)

        ranked = sorted([t for t in TOPICS["lounge"] if t in w], key=lweight, reverse=True)   # scored topics only
        chosen = [t for t in ranked if lweight(t) >= IMPORTANT]
        return (chosen + [t for t in ranked if t not in chosen])[:max(MIN_ITEMS, len(chosen))]
    if kind == "area":
        if facts["women"] < facts["skip_under_women"]:
            return ["size", "reach"]
        topics = (["size"] + (["demand"] if facts.get("demand_pct") is not None else [])
                  + (["cost"] if facts.get("rent_ratio") is not None else []) + ["reach"])
        if facts["worker_share"] >= facts["worker_cap"]:
            topics.append("worker_housing")
        if facts["data_coverage"] < facts["min_coverage"]:
            topics.append("data_gap")
        return topics
    skip = {"shrink": facts["shrink_count"] == 0, "grow": facts["grow_count"] == 0,
            "protect": facts["protect_count"] == 0}
    return [t for t in TOPICS[kind] if not skip.get(t)][:MAX_ITEMS]


GROWTH_WHY = (
    "Each area is a what-if: open a typical lounge there and count the women it would add to the "
    f"network, net of those it takes from our own lounges (Huff). GROW needs at least {growth.NEW_SITE_MIN:,} "
    f"net new women, worker housing under {growth.WORKER_CAP:.0%} of adults, a shop rent no more expensive than the median "
    "salon site in its emirate (rent ratio 1 or more, or no rent known, or the emirate-median fallback: "
    "neutral, low confidence) and a site that would out-serve at least "
    f"{growth.DEMAND_PCT_MIN:.0%} of its emirate's salon sites (UAE-wide under 50; frozen reference). WATCH: big "
    "enough but more expensive or weaker demand, mostly "
    f"worker housing, or {growth.NEW_SITE_MIN // 2:,}+ net new women. SKIP: fewer, under "
    f"{growth.SKIP_UNDER_WOMEN:,} women, or non-residential by name. Under {growth.MIN_COVERAGE:.0%} of the "
    "women searched for competitors lowers confidence.")


def _thresholds_note(kind: str) -> str:
    if kind == "lounge":
        return f"{scorecard.THRESHOLDS_WHY} {scorecard.FLIP_WHY}"
    if kind == "area":
        return GROWTH_WHY
    return f"{scorecard.THRESHOLDS_WHY} {GROWTH_WHY}"   # uae


def _ev(field: str, facts: dict) -> Evidence:
    return Evidence(field=field, label=GLOSSARY[field].label, value=facts.get(field))


# --- template (no AI) ---------------------------------------------------------------

def _template_claim(kind: str, topic: str, f: dict) -> str:
    if kind == "lounge" and f.get(f"score_{topic}") is None:  # NOT SCORED: no scores
        main = TOPICS["lounge"][topic][0]
        return f"{GLOSSARY[main].label}: {fmt_unit(main, f[main])}, shown but not scored."
    if kind == "lounge" and topic == "cost" and f.get("rent_fallback"):
        return f"Rent scores neutral: the site's shop rent is the {f['emirate']} median, not observed."
    if kind == "lounge":
        score = f[f"score_{topic}"]
        strength = "a strength" if score >= 0.6 else "a weakness" if score <= 0.4 else "middling"
        main = TOPICS[kind][topic][0]
        return f"{GLOSSARY[main].label} is {strength}: {fmt_unit(main, f[main])}."
    if kind == "area":
        sat = f["premium_reviews_per_1k"]
        return {
            "size": (f"A new lounge here would add about {fmt('new_site_net', f['new_site_net'])} net new "
                     f"women (GROW needs {fmt('new_site_min', f['new_site_min'])})."),
            "demand": (f"A new lounge here would out-serve {fmt('demand_pct', f['demand_pct'])} of "
                       f"{f['demand_ref']} salon sites ({fmt('demand_pct_uae', f['demand_pct_uae'])} UAE-wide; "
                       f"GROW needs {growth.DEMAND_PCT_MIN:.0%})."),
            "cost": (f"Rent is the {f['emirate']} median standing in, not observed: the rent test is neutral."
                     if f.get("rent_fallback") else
                     f"Rent ratio {fmt('rent_ratio', f['rent_ratio'])} against the median {f['emirate']} salon "
                     f"site (GROW needs 1 or more)."),
            "saturation": (f"{fmt('premium_reviews_per_1k', sat)} premium reviews per 1k women, "
                           f"{'under' if f['unsaturated'] else 'over'} the "
                           f"{fmt('unsaturated_per_1k', f['unsaturated_per_1k'])} line."),
            "reach": (f"The nearest lounge, {f['nearest_lounge_id']}, is "
                      f"{fmt('nearest_lounge_km', f['nearest_lounge_km'])} km away in a straight "
                      "line."),
            "worker_housing": (f"{fmt('worker_share', f['worker_share'])} of adults live in "
                               "worker housing, so the women estimate is uncertain."),
            "data_gap": (f"Our salon search covered {fmt('data_coverage', f['data_coverage'])} "
                         "of the women here, so competition is partly unknown."),
        }[topic]
    return {  # uae
        "shrink": (f"Review {f['shrink_high_count']} weak lounge site(s) ({f['shrink_high_lounges']}), of "
                   f"{f['shrink_count']} SHRINK calls."),
        "protect": (f"Defend {f['protect_high_count']} strong site(s) ({f['protect_high_lounges']}), of "
                    f"{f['protect_count']} PROTECT calls."),
        "grow": (f"Search for sites in {f['grow_high_count']} high-confidence GROW areas, of "
                 f"{f['grow_count']} GROW areas."),
        "confidence": (f"{f['low_confidence_count']} of {f['lounges_scored']} lounge calls are low "
                       "confidence, and there is no revenue or lease data."),
    }[topic]


def _template_headline(kind: str, action: str, f: dict) -> str:
    if kind == "lounge":
        if action == NOT_SCORED_ACTION:
            return ("Not scored: this lounge serves travellers, not the women living around it, "
                    "so the catchment model doesn't apply.")
        return (f"{action}: composite {f['composite']:.2f} (PROTECT at {scorecard.PROTECT_AT} or "
                f"more, SHRINK at {scorecard.SHRINK_AT} or less).")
    if kind == "area":
        rent, dem = f.get("rent_gap"), f.get("demand_gap")
        return (f"{action}: {'big enough' if f['big_enough'] else 'not big enough'}, "
                + ("demand unknown" if dem is None else "strong demand" if dem >= 0 else "weaker demand")
                + " for its emirate, and "
                + ("rent unknown" if rent is None else "no more expensive than" if rent >= 0 else "more expensive than")
                + ("" if rent is None else " its emirate's median salon site") + ".")
    return (f"Review {f['shrink_high_count']}, defend {f['protect_high_count']} and search for sites in "
            f"{f['grow_high_count']} areas (high-confidence calls).")


_TEMPLATE_CAPTIONS = {
    "lounge": ("Each signal is scored 0-1 on a fixed scale, where 1 is good for the lounge, and "
               "the composite is their weighted average. Both rank the site within its emirate's "
               "frozen market of competitor salon sites: demand is the share of them a typical lounge "
               "here would out-serve (Huff); rent is their median shop rent over this site's. The lounge's own "
               "served women, as performance vs its site, capture, rating and the shared catchment "
               "are shown for context, not scored."),
    "area": ("Each area is a what-if new lounge: big enough when it would add enough net new "
             "women to the network, and GROW when it would also out-serve at least half its emirate's "
             "salon sites and its rent is no more expensive than theirs (median)."),
    "uae": ("Lounge calls come from a fixed-scale scorecard scoring each site within its emirate's salon sites (demand and rent); "
            "growth-area calls from a what-if new lounge's net new women, demand percentile and rent ratio."),
}


# What each call asks the network and capital owner to do (docs/glossary.md, Decisions). verify() requires the phrase in now_what.
ACTIONS = {
    "PROTECT": ("defend", ("Keep and defend the site: renew at the lease event, don't relocate, "
                           "and treat a competitor opening nearby as a threat to respond to.")),
    "HOLD": ("no portfolio action", ("No portfolio action this cycle: revisit at the next lease "
                                     "event, or sooner if a signal crosses a line.")),
    "SHRINK": ("investigate", ("Investigate, don't close: before the lease event, review whether "
                               "to downsize; consolidate only where a sibling would take most of "
                               "its customers (the absorbed share if it closed).")),
    "GROW": ("site search", ("Start a site search here: a shortlist for a site visit and lease "
                             "search, verified on the ground before committing.")),
    "WATCH": ("revisit", "Don't act now: revisit when the failing test changes."),
    "SKIP": ("no action", "No action: a new lounge here would add too few women."),
}
LABELS = {"lounge": ("PROTECT", "HOLD", "SHRINK"), "area": ("GROW", "WATCH", "SKIP")}
# Advice on running a branch (ratings, rosters and hiring, service quality) is out of scope (rubric OB4); capacity
# per catchment is in scope but unmeasured today (no bookings or headcount), so explanations never prescribe staff.
IN_BRANCH = re.compile(
    r"\b(improv|rais|boost|lift|fix|lever)\w*\b[^.;]{0,40}\b(rating|service|staff|quality)"
    r"|\b(rating|service)\b[^.;]{0,40}\blever|\bstaff(ing)?\b|\btraining\b|service quality",
    re.IGNORECASE)


def performance_sentence(x: float | None) -> str:
    """The owner's wording for performance_vs_site (context, not scored)."""
    if x is None:
        return "The model has no site estimate to compare this lounge with"
    return f"The model estimates this lounge is performing {x:.1f}x compared to its site"


def _template_so_what(kind: str, action: str, f: dict) -> str:
    if kind == "lounge":
        if action == NOT_SCORED_ACTION:
            return "Its customers are travellers, so the catchment says nothing about its market."
        return (f"{performance_sentence(f.get('performance_vs_site'))} (context, not scored). "
                f"{fmt('catchment_women', f['catchment_women'])} women live within a 15-min drive; "
                f"{fmt('shared_share', f['shared_share'])} of them are also reached by another lounge.")
    if kind == "area":
        return (f"{fmt('women', f['women'])} women 15+ live here; our nearest lounge is "
                f"{f['nearest_lounge_id']}.")
    return ""   # uae: the summary is one paragraph, headline and arguments only


def _template_now_what(kind: str, action: str, f: dict) -> str:
    if action not in ACTIONS:
        return "No portfolio call from this model." if kind == "lounge" else ""
    return " ".join([ACTIONS[action][1], *what_would_change(kind, f)])


def template_explanation(kind: str, subject_id: str, action: str, facts: dict) -> Explanation:
    topics = prioritize(kind, facts, action)
    reasons = [Reason(topic=t, claim=_template_claim(kind, t, facts),
                      evidence=[_ev(k, facts) for k in TOPICS[kind][t][:MAX_ITEMS]
                                if k in facts and not (kind == "lounge" and k.startswith("score_")
                                                       and facts[k] is None)])
               for t in topics]
    return Explanation(subject_id=subject_id, kind=kind, action=action,
                       headline=_template_headline(kind, action, facts), reasons=reasons,
                       so_what=_template_so_what(kind, action, facts),
                       now_what=_template_now_what(kind, action, facts),
                       table_caption=_TEMPLATE_CAPTIONS[kind],
                       thresholds_note=_thresholds_note(kind), source="template")


# --- grounding check ------------------------------------------------------------------

_NUMBER = re.compile(r"(?<![\w.])-?\d[\d,]*\.?\d*")  # "0-1" is a range, not -1


def _allowed_numbers(facts: dict) -> list[float]:
    nums = [float(v) for v in facts.values()
            if isinstance(v, (int, float)) and not isinstance(v, bool)]
    nums += [abs(v) for v in nums if v < 0]  # gaps quoted as "2,100 short" / "0.2 stars below"
    nums += [v * 100 for v in nums if 0 <= v <= 1]  # shares and scores quoted as %
    nums += [4, 0, 1]
    nums += [scorecard.PROTECT_AT, scorecard.SHRINK_AT, scorecard.FLIP_LOW, scorecard.COMBOS, 15, 60, 1_000]
    nums += [x for s in scorecard.SIGNALS for x in (s.worst, s.best, s.weight)]
    nums += [growth.NEW_SITE_MIN, growth.NEW_SITE_MIN // 2, growth.SKIP_UNDER_WOMEN, growth.UNSATURATED_PER_1K,
             growth.WORKER_CAP * 100, growth.MIN_COVERAGE * 100]
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
    for name in ("so_what", "now_what"):
        if kind != "uae" and not getattr(exp, name, "").strip():
            errors.append(f"{name} is required")
    if exp.action in LABELS.get(kind, ()):  # E5: the text names the decision's own label
        first = re.search(r"\b(" + "|".join(LABELS[kind]) + r")\b", exp.headline)
        if not first or first.group() != exp.action:
            errors.append(f"headline must name the call {exp.action} before any other label")
        if ACTIONS[exp.action][0] not in getattr(exp, "now_what", "").lower():
            errors.append(f"now_what must give the {exp.action} action "
                          f"({ACTIONS[exp.action][0]!r}): {ACTIONS[exp.action][1]}")
    if kind == "lounge" and facts.get("performance_vs_site") is not None and exp.action in LABELS["lounge"]:
        want = performance_sentence(facts["performance_vs_site"])
        if want not in getattr(exp, "so_what", ""):
            errors.append(f"so_what must quote, word for word, {want!r} and say it is context, not scored")
    texts = [exp.headline, exp.table_caption, getattr(exp, "so_what", ""),
             getattr(exp, "now_what", "")] + [r.claim for r in exp.reasons]
    if any(IN_BRANCH.search(t) for t in texts):
        errors.append("in-branch advice (rating, staffing, service quality) is out of scope: "
                      "explain where capacity sits, never how to run a branch")
    if kind == "uae":
        paragraph = [exp.headline] + [r.claim for r in exp.reasons]
        if any(re.search(r"\bopen", t, re.IGNORECASE) for t in paragraph):
            errors.append("GROW starts a site search: never say open")
        if any(re.search(r"\bclos(e|ing|ure)\b(?!\s+to\b)", t, re.IGNORECASE) for t in paragraph):
            errors.append("SHRINK means review, never close")
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
    # Also as written in prose: "Mirdif 35" for mirdif-35.
    ids = {part for v in facts.values() if isinstance(v, str) for part in v.split(", ")} | {exp.subject_id}
    ids = sorted(ids | {i.replace("-", " ") for i in ids}, key=len, reverse=True)
    for text in texts:
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
    "will defend them to the network and capital owner (who decides where capital sits, not how a "
    "branch is run) and "
    "a private-equity board. The decision is already made by a rule-based model; you explain "
    "it, you never change it. Answer what / so what / now what. What: a pyramid, a one-sentence "
    "answer (headline) that names the call in capitals (e.g. HOLD) before any other call, then "
    "the supporting arguments you are given, in the order given, each a one-sentence claim "
    "backed by 2-5 data points copied from the fact sheet. So what: 1-2 sentences on the "
    "business consequence in the portfolio team's terms: women and customers at stake, the competitive "
    "position, what is shared with sibling lounges. Now what: 1-2 sentences giving the action "
    "the call asks for (the action_definition you are given, in your own words but keeping its "
    "key phrase) and what would change the call, citing the distance-to-line facts "
    "(line_gap, next_call, flip_driver, flip_value; for areas size_gap, demand_gap, rent_gap, saturation_gap, "
    "worker_gap, coverage_gap). Our scope ends at the site: never advise on anything inside a "
    "branch (ratings, reviews to chase, rosters or hiring, service quality, operations); rating is "
    "context, not a lever. Use only the fact sheet. Every number you write must appear in the "
    "fact sheet or the thresholds; round sensibly. Write like a board memo: short, concrete "
    "claims. Never mention revenue or profit (none exist). Quote shop rent only when the fact "
    "sheet has it, as our cost (never customer affluence, never a lever to renegotiate), and say "
    "the 150 m² unit is assumed when quoting women per rent. For a lounge, the call scores its SITE "
    "(its demand percentile and rent ratio among its emirate's competitor salon sites), not the lounge's "
    "own sales; quote the UAE-wide percentiles as context where you cite either signal: so_what "
    "must quote performance_vs_site word for word as 'The model estimates this lounge is performing "
    "N.Nx compared to its site' (1 decimal) and say it is context, not scored. Always answer by "
    "calling the submit_explanation tool."
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
            "so_what": {
                "type": "string",
                "description": "1-2 sentences: the business consequence for the portfolio team (women and "
                               "customers at stake, competitive position, overlap with sibling "
                               "lounges). No revenue or profit: the model has none (site cost is rent-based).",
            },
            "now_what": {
                "type": "string",
                "description": "1-2 sentences: the action this call asks for (keep the "
                               "action_definition's key phrase) and what would change the call, "
                               "citing the distance-to-line facts. Nothing inside a branch.",
            },
            "table_caption": {
                "type": "string",
                "description": "2-3 sentences explaining, for a non-technical executive, what "
                               "the factors measure and how to read them for this lounge, "
                               "area or the UAE network.",
            },
        },
        "required": ["headline", "reasons", "so_what", "now_what", "table_caption"],
        "additionalProperties": False,
    },
}


def _user_message(kind: str, subject_id: str, action: str, facts: dict, errors: list[str]) -> str:
    msg = {
        "subject": f"{kind} {subject_id}",
        "decision": action,
        "action_definition": ACTIONS[action][1] if action in ACTIONS else None,
        "what_would_change": what_would_change(kind, facts),
        "arguments_in_order": [
            {"topic": t, "label": TOPIC_LABELS[t], "cite_at_least_one_of": TOPICS[kind][t]}
            for t in prioritize(kind, facts, action)],
        "fact_sheet": facts,
        "field_glossary": {k: {"label": GLOSSARY[k].label, "unit": GLOSSARY[k].unit,
                               "meaning": GLOSSARY[k].meaning} for k in facts},
        "thresholds": _thresholds_note(kind),
    }
    if kind == "uae":
        msg["format"] = NETWORK_FORMAT
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
        so_what=raw.get("so_what", ""), now_what=raw.get("now_what", ""),
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
    if key in cache:   # the thresholds note is derived, not written: always today's
        return Explanation(**{**cache[key], "thresholds_note": _thresholds_note(kind)})
    if client is not None and action != NOT_SCORED_ACTION:
        exp = llm_explanation(client, kind, subject_id, action, facts)
        if exp is not None:
            cache[key] = exp.model_dump()
            return exp
    return template_explanation(kind, subject_id, action, facts)


NETWORK_ACTION = "SUMMARY"
# The Executive Summary's one-paragraph summary: the page, read top-down (the pyramid principle).
NETWORK_FORMAT = (
    "This is the Executive Summary's one-paragraph summary, shown as plain text: the headline and then "
    "each argument's claim, read together as 4-5 sentences. Headline: the answer, as actions (review, "
    "defend, search for sites), counting high-confidence calls. Then one sentence per argument, each "
    "giving its high-confidence count first and the all-confidence count second. The last sentence says "
    "how sure to be and why (calls near a line, no revenue or lease data). GROW starts a site search: "
    "never write open. SHRINK means review: never write close. Growth areas overlap, so never add their "
    "figures. Plain words, no ids in brackets unless they are lounge names. Leave so_what and now_what "
    "empty; the table_caption is one sentence.")
V3_NETWORK_ID = "uae"


def v3_subjects() -> list[tuple[str, str, str, dict]]:
    """(kind, id, action, facts) for every v3 explanation at the baseline (medium levels)."""
    from src.baseline import run
    return run_subjects(run())


def run_subjects(r) -> list[tuple[str, str, str, dict]]:
    """(kind, id, action, facts) for every explanation of one baseline.Run (the app uses this too,
    so its fact sheets hit the committed cache exactly when the numbers match the baseline)."""
    subjects = [("uae", V3_NETWORK_ID, NETWORK_ACTION, uae_facts(r))]
    subjects += [("lounge", f.branch_id, d.action, lounge_facts(f, d, r.flips.get(f.branch_id)))
                 for f, d in zip(r.features, r.decisions)]
    subjects += [("area", a.area_id, d.action, area_facts(a, d))
                 for a, d in zip(r.areas, r.area_decisions)]
    return subjects


def needs_ai(action: str) -> bool:
    """AI explanations are written for every v3 subject except the fixed NOT SCORED template and
    SKIP areas (hundreds of small places; their template says enough)."""
    return action not in (NOT_SCORED_ACTION, "SKIP")


def write_prompts(out_dir) -> int:
    """One JSON prompt per v3 subject not yet in the cache, for a writer outside the API."""
    from pathlib import Path
    out = Path(out_dir)
    (out / "answers").mkdir(parents=True, exist_ok=True)
    cache, n = load_cache(), 0
    for kind, sid, action, facts in v3_subjects():
        if not needs_ai(action) or cache_key(kind, sid, action, facts) in cache:
            continue
        (out / f"{kind}__{sid}.json").write_text(json.dumps({
            "system": SYSTEM_PROMPT, "request": json.loads(_user_message(kind, sid, action, facts, [])),
            "answer_schema": EXPLAIN_TOOL["input_schema"],
            "answer_file": str(out / "answers" / f"{kind}__{sid}.json")}, indent=2, ensure_ascii=False))
        n += 1
    return n


def ingest_answers(out_dir, write: bool = True) -> tuple[int, dict[str, list[str]]]:
    """Verify every answer file and cache the grounded ones (write=False: only check).
    Returns (grounded, errors by file)."""
    from pathlib import Path
    answers = Path(out_dir) / "answers"
    subjects = v3_subjects()
    current = {cache_key(*s) for s in subjects}  # drop entries for numbers that no longer exist
    cache = {k: v for k, v in load_cache().items() if k in current}
    ok, failed = 0, {}
    for kind, sid, action, facts in subjects:
        path = answers / f"{kind}__{sid}.json"
        if not path.exists():
            continue
        exp = _parse(json.loads(path.read_text()), kind, sid, action)
        errors = verify(exp, facts, kind)
        if errors:
            failed[path.name] = errors
            continue
        cache[cache_key(kind, sid, action, facts)] = exp.model_dump()
        ok += 1
    if write:
        CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False, sort_keys=True))
    return ok, failed


def make_client():
    """Client from ANTHROPIC_API_KEY, or None when it isn't set."""
    if not settings.anthropic_api_key:
        return None
    import anthropic
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def main() -> None:
    """Regenerate AI explanations for the baseline through the API and write the committed cache.
    Same subjects as the offline `prompts` path: NOT SCORED lounges and SKIP areas keep their
    template."""
    import anthropic

    client = make_client()
    if client is None:
        raise SystemExit("Set ANTHROPIC_API_KEY in .env first (or use the offline path: "
                         "`python -m src.explain prompts DIR`).")
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
    subjects = [s for s in v3_subjects() if needs_ai(s[2])]
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


USAGE = """usage: python -m src.explain COMMAND
  prompts DIR   write the offline prompts (no API)
  check DIR     check answers in DIR against their fact sheets (no API)
  ingest DIR    check, then write the grounded answers to the cache (no API)
  api           regenerate through the paid Anthropic API (needs ANTHROPIC_API_KEY)"""

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if sys.argv[1:2] == ["prompts"]:
        print(f"wrote {write_prompts(sys.argv[2])} prompts to {sys.argv[2]}")
    elif sys.argv[1:2] in (["ingest"], ["check"]):
        cached, failed = ingest_answers(sys.argv[2], write=sys.argv[1] == "ingest")
        for name, errors in failed.items():
            print(f"FAILED {name}: {errors}")
        print(f"{cached} grounded explanations{' cached' if sys.argv[1] == 'ingest' else ''}; "
              f"{len(failed)} failed the checks")
    elif sys.argv[1:] == ["api"]:   # the only paid path: it must be asked for by name
        main()
    else:   # --help, a typo or no argument never reaches the API
        raise SystemExit(USAGE)
