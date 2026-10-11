"""Growth areas: GROW / WATCH / SKIP from a what-if (`classify`): open a typical lounge in the area
(src/model/served.what_if_open) and count the women it would add to the network, net of those it takes
from our own lounges.

  GROW   net new women >= NEW_SITE_MIN, worker housing under WORKER_CAP of adults, and cost index >= 1
         (as cost-efficient as the emirate's typical lounge) or unknown.
  WATCH  big enough but dearer; or big enough but mostly worker housing; or NEW_SITE_MIN / 2 or more.
  SKIP   fewer net new women; under SKIP_UNDER_WOMEN women (raw); or a NON_RESIDENTIAL name.
  Saturation (premium reviews per 1k women vs UNSATURATED_PER_1K) is context, not a test: competition
  already shapes the Huff split. Under MIN_COVERAGE of the women searched lowers confidence.
  GROW_MIN_WOMEN and _confidence below belong to the retired two-test rule (no caller uses them for the call).
"""
import re

from src.models import Area, AreaDecision

GROW_MIN_WOMEN = 20_000
SKIP_UNDER_WOMEN = 5_000
WORKER_CAP = 0.5
MIN_COVERAGE = 0.5
UNSATURATED_PER_1K = 150.0
NON_RESIDENTIAL = re.compile(
    r"\b(industrial|free zone|military|airport)\b|\bport\b(?!\s+saeed)"
    r"|صناعي|منطقة حرة|عسكري|مطار|ميناء", re.IGNORECASE)
NEAR_LINE = 0.10    # within 10% of the size or saturation line: low confidence
FAR_LINE = 0.20     # 20%+ from both: high confidence

WHY = {
    "GROW_MIN_WOMEN": "Retired with the two-test rule (2026-10-11; not used in the call). Was: just under the smallest lounge catchment (23k women at medium levels): the least a lounge runs on today.",
    "SKIP_UNDER_WOMEN": "Under 5,000 women an area can't carry a lounge whatever the competition.",
    "WORKER_CAP": "Where most adults live in worker housing, the women estimate rests on the worker-housing female share.",
    "MIN_COVERAGE": ("Under half the women in searched cells, the saturation figure describes the minority "
                     "and the rest of the competition is imputed: the call is low confidence."),
    "UNSATURATED_PER_1K": (
        "Recalibrated on 2026-10-10 by a rule fixed before seeing the result: the 25th percentile of "
        "premium reviews per 1k women over the scored lounge catchments with a real premium market "
        "(10+ premium salons), at baseline levels, rounded to the nearest 10. Those 21 catchments run "
        "88-630 (al-jada 88, median 220), p25 152.8 -> 150; the two thin ones (al-dhafra 10, al-falah 27) "
        "are left out. Why not the old 50, under every working catchment: back-test BT5 found clustering "
        "doesn't hurt (isolated premium salons have a median 126 reviews, those with 3+ neighbours within "
        "1.5 km about 220), so a market as crowded as the lighter quarter of the ones our lounges "
        "succeed in is not a reason to stay out. Same measure as the lounges' (one helper, rubric MO8)."),
    "NON_RESIDENTIAL": (
        "Areas named industrial, free zone, military, airport or port (and the Arabic equivalents) are "
        "not where customers live, whatever WorldPop counts there: SKIP before any test. Port Saeed is "
        "excluded from the pattern: it is a residential and retail district of Deira, not a port."),
    "NEAR_LINE": ("An area within 10% of the size or saturation line is low confidence, as are areas with "
                  "unknown saturation, under half their women searched, or big only on thin affluence data; "
                  "20%+ from both lines is high, mirroring the lounges' 0.05 / 0.10 margins."),
}


def _confidence(a: Area, unsat: bool | None, thin_affluence: bool) -> tuple[str, list[str]]:
    """low / medium / high, and why it is low (shown with the caveats)."""
    gaps = [(a.addressable_women - GROW_MIN_WOMEN) / GROW_MIN_WOMEN]
    reasons = []
    if abs(gaps[0]) < NEAR_LINE:
        reasons.append(f"Within {NEAR_LINE:.0%} of the size line ({a.addressable_women:,.0f} addressable "
                       f"women vs {GROW_MIN_WOMEN:,}).")
    if a.premium_reviews_per_1k is not None:
        gaps.append((a.premium_reviews_per_1k - UNSATURATED_PER_1K) / UNSATURATED_PER_1K)
        if abs(gaps[1]) < NEAR_LINE:
            reasons.append(f"Within {NEAR_LINE:.0%} of the saturation line ({a.premium_reviews_per_1k:.0f} vs "
                           f"{UNSATURATED_PER_1K:g} premium reviews per 1k women).")
    low = bool(reasons) or unsat is None or a.data_coverage < MIN_COVERAGE or thin_affluence
    level = "low" if low else "high" if min(map(abs, gaps)) >= FAR_LINE else "medium"
    return level, reasons


NEW_SITE_MIN = 6_000
NEW_SITE_MIN_WHY = ("Quick first cut (2026-10-11): a new lounge here should add at least about what our median "
                    "lounge serves today (~6k women, Huff), net of what it takes from our own lounges.")
WHY = {"NEW_SITE_MIN": NEW_SITE_MIN_WHY, **WHY}  # shown first on the How page


def classify(a: Area) -> AreaDecision:
    """What-if: open a typical lounge here (src/model/served.what_if_open). GROW / WATCH / SKIP on the
    women it would add to the network, and its cost efficiency where a shop rent is known."""
    net = a.new_site_net or 0.0
    cheap = a.cost_index is None or a.cost_index >= 1
    big = net >= NEW_SITE_MIN and a.worker_share < WORKER_CAP
    unsat = None if a.premium_reviews_per_1k is None else a.premium_reviews_per_1k < UNSATURATED_PER_1K
    caveats = []
    if a.data_coverage < MIN_COVERAGE:
        caveats.append(f"Only {a.data_coverage:.0%} of its women were searched for competitors: the rest are "
                       "imputed from comparable places in the emirate.")
    if a.cost_index is None and a.new_site_net is not None:
        caveats.append("No shop rent here: cost efficiency unknown.")
    gap = (net - NEW_SITE_MIN) / NEW_SITE_MIN
    confidence = "low" if abs(gap) < NEAR_LINE or a.data_coverage < MIN_COVERAGE else "high" if abs(gap) >= FAR_LINE else "medium"
    if NON_RESIDENTIAL.search(a.name):
        action, why, confidence = "SKIP", f"Non-residential by name ({a.name}): not where customers live.", "high"
    elif a.women < SKIP_UNDER_WOMEN:
        action, why, confidence = "SKIP", f"Only {a.women:,.0f} women 15+, under the {SKIP_UNDER_WOMEN:,} floor.", "high"
    elif big and cheap:
        action, why = "GROW", (f"A new lounge would add about {net:,.0f} women to the network"
                               + ("" if a.cost_index is None else f", at {a.cost_index:.1f}x our typical cost efficiency") + ".")
    elif big:
        action, why = "WATCH", f"Enough new women ({net:,.0f}), but dearer per woman than our typical lounge ({a.cost_index:.1f}x)."
    elif net >= NEW_SITE_MIN:
        action, why = "WATCH", f"Enough new women ({net:,.0f}), but mostly worker housing ({a.worker_share:.0%} of adults)."
    elif net >= NEW_SITE_MIN / 2:
        action, why = "WATCH", f"A new lounge would add about {net:,.0f} women: half a typical lounge (GROW needs {NEW_SITE_MIN:,})."
    else:
        action, why = "SKIP", f"A new lounge would add only about {net:,.0f} women."
    why += f" Nearest lounge: {a.nearest_lounge_id}, {a.nearest_lounge_km:.1f} km in a straight line."
    return AreaDecision(area_id=a.area_id, action=action, big_enough=big, unsaturated=unsat,
                        rationale=why, caveats=caveats, confidence=confidence)


def classify_all(areas: list[Area]) -> list[AreaDecision]:
    return [classify(a) for a in areas]
