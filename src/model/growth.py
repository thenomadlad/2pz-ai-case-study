"""Growth areas: GROW / WATCH / SKIP from two questions (every area is already beyond the current travel-time
catchment, 15 min at baseline, of every open scored lounge, by construction in src/features/lounges.py).

  Big enough?   at least GROW_MIN_WOMEN addressable women 15+ (affluence-weighted), and worker
                housing under WORKER_CAP of adults.
  Unsaturated?  premium-salon reviews per 1k women (over the cells we searched) under
                UNSATURATED_PER_1K; None when no cell was searched.

  both -> GROW, one -> WATCH (also: big but mostly worker housing), neither -> SKIP; under
  SKIP_UNDER_WOMEN women (raw) -> SKIP; small, unsaturated and mostly worker housing -> SKIP; a
  NON_RESIDENTIAL name (industrial, free zone, military, airport, port) -> SKIP before any test.
  Unknown saturation, or under MIN_COVERAGE of the women searched, caps at WATCH, and so does a size
  test passed only through the affluence weighting (raw women under GROW_MIN_WOMEN) when under
  MIN_COVERAGE of the women have an observed rent. Thresholds reviewed by the user on 2026-10-09
  (notebooks/decisions.ipynb); UNSATURATED_PER_1K recalibrated by a fixed rule on 2026-10-10.
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
    "GROW_MIN_WOMEN": "Just under the smallest lounge catchment (23k women at medium levels): the least a lounge runs on today.",
    "SKIP_UNDER_WOMEN": "Under 5,000 women an area can't carry a lounge whatever the competition.",
    "WORKER_CAP": "Where most adults live in worker housing, the women estimate rests on the worker-housing female share.",
    "MIN_COVERAGE": ("Under half the women in searched cells, the saturation figure describes the minority. "
                     "Likewise an area big enough only through the affluence weighting, with rents "
                     "observed for under half its women, caps at WATCH."),
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


UNSERVED_MIN = 10_000
UNSERVED_MIN_WHY = ("Quick first cut (2026-10-11): an area is GROW when the Huff model leaves at least this "
                    "many addressable women unserved: about what a mid-sized lounge serves today (median ~6k, "
                    "top ~19k), so a new lounge there would not have to take customers from anyone.")


def classify(a: Area) -> AreaDecision:
    """GROW / WATCH / SKIP on unserved demand (src/model/served.py), anywhere, reached or not."""
    big = a.unserved_women >= UNSERVED_MIN and a.worker_share < WORKER_CAP
    unsat = None if a.premium_reviews_per_1k is None else a.premium_reviews_per_1k < UNSATURATED_PER_1K
    caveats = []
    thin_affluence = big and a.women < UNSERVED_MIN and a.affluence_coverage < MIN_COVERAGE
    if thin_affluence:
        caveats.append(f"Affluence data covers only {a.affluence_coverage:.0%} of the women here, and the "
                       f"unserved figure leans on it ({a.women:,.0f} women before weighting).")
    gap = (a.unserved_women - UNSERVED_MIN) / UNSERVED_MIN
    confidence = "low" if abs(gap) < NEAR_LINE or thin_affluence else "high" if abs(gap) >= FAR_LINE else "medium"
    if NON_RESIDENTIAL.search(a.name) or a.women < SKIP_UNDER_WOMEN:
        confidence = "high"
    if NON_RESIDENTIAL.search(a.name):
        action, why = "SKIP", f"Non-residential by name ({a.name}): not where customers live."
    elif a.women < SKIP_UNDER_WOMEN:
        action, why = "SKIP", f"Only {a.women:,.0f} women 15+, under the {SKIP_UNDER_WOMEN:,} floor."
    elif big and not thin_affluence:
        action, why = "GROW", f"{a.unserved_women:,.0f} addressable women no premium salon serves."
    elif big:
        action, why = "WATCH", "Enough unserved women only through the affluence weighting, on thin rent data."
    elif a.unserved_women >= UNSERVED_MIN:
        action, why = "WATCH", f"Enough unserved women, but mostly worker housing ({a.worker_share:.0%} of adults)."
    elif a.unserved_women >= UNSERVED_MIN / 2:
        action, why = "WATCH", (f"{a.unserved_women:,.0f} unserved addressable women: half a lounge's market "
                                f"(GROW needs {UNSERVED_MIN:,}).")
    else:
        action, why = "SKIP", f"Only {a.unserved_women:,.0f} unserved addressable women; the rest is served."
    why += f" Nearest lounge: {a.nearest_lounge_id}, {a.nearest_lounge_km:.1f} km in a straight line."
    return AreaDecision(area_id=a.area_id, action=action, big_enough=big, unsaturated=unsat,
                        rationale=why, caveats=caveats, confidence=confidence)


def classify_all(areas: list[Area]) -> list[AreaDecision]:
    return [classify(a) for a in areas]
