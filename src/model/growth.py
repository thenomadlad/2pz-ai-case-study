"""Growth areas: GROW / WATCH / SKIP from a what-if (`classify`): open a typical lounge in the area
(src/model/served.what_if_open) and count the women it would add to the network, net of those it takes
from our own lounges.

  GROW   net new women >= NEW_SITE_MIN, worker housing under WORKER_CAP of adults, rent_ratio >= 1
         (no more expensive than the median salon site in its emirate; unknown or emirate-median fallback passes: RENT_FALLBACK_WHY) and demand_pct >=
         DEMAND_PCT_MIN (a new lounge here would out-serve at least half its emirate's salon sites;
         src/features/lounges.SITE_REFERENCE_WHY).
  WATCH  big enough but more expensive or weaker demand; or big enough but mostly worker housing; or
         NEW_SITE_MIN / 2 or more.
  SKIP   fewer net new women; under SKIP_UNDER_WOMEN women (raw); or a NON_RESIDENTIAL name.
  Saturation (premium reviews per 1k women vs UNSATURATED_PER_1K) is context, not a test: competition
  already shapes the Huff split. Under MIN_COVERAGE of the women searched lowers confidence.
"""
import re

from src.models import Area, AreaDecision, Rules

SKIP_UNDER_WOMEN = 5_000
WORKER_CAP = 0.5
MIN_COVERAGE = 0.5
UNSATURATED_PER_1K = 150.0
NON_RESIDENTIAL = re.compile(
    r"\b(industrial|free zone|military|airport)\b|\bport\b(?!\s+saeed)"
    r"|صناعي|منطقة حرة|عسكري|مطار|ميناء", re.IGNORECASE)
NEAR_LINE = 0.10    # within 10% of the net-new-women line: low confidence
FAR_LINE = 0.20     # 20%+ from it: high confidence

WHY = {
    "SKIP_UNDER_WOMEN": "Under 5,000 women an area can't carry a lounge whatever the competition.",
    "WORKER_CAP": "Where most adults live in worker housing, the women estimate rests on the worker-housing female share.",
    "MIN_COVERAGE": ("Under half the women in searched cells, the saturation figure describes the minority "
                     "and the rest of the competition is imputed: the call is low confidence."),
    "UNSATURATED_PER_1K": (
        "Context only, not a test: no call uses it. Competition already shapes the Huff split behind net new "
        "women and the demand percentile, so testing saturation too would count it twice. The line marks an "
        "area as unsaturated for display: the 25th percentile of premium reviews per 1k women over the scored "
        "lounge catchments with 10+ premium salons, at baseline levels, rounded to the nearest 10 (2026-10-10: "
        "21 catchments, 88-630, p25 152.8 -> 150; al-dhafra and al-falah left out as thin). Same measure as "
        "the lounges' (one helper, rubric MO8)."),
    "NON_RESIDENTIAL": (
        "Areas named industrial, free zone, military, airport or port (and the Arabic equivalents) are "
        "not where customers live, whatever WorldPop counts there: SKIP before any test. Port Saeed is "
        "excluded from the pattern: it is a residential and retail district of Deira, not a port."),
    "NEAR_LINE": ("An area within 10% of the net-new-women line (NEW_SITE_MIN) is low confidence, as are areas "
                  "with under half their women searched; 20%+ from the line is high, mirroring the lounges' "
                  "0.05 / 0.10 margins."),
}


DEMAND_PCT_MIN = Rules().demand_pct_min
DEMAND_PCT_MIN_WHY = ("GROW needs the site to out-serve at least half of its emirate's reference salon sites "
                      "(UAE-wide where an emirate has under 50): a typical lounge here would serve at least what "
                      "one would at the median competitor salon site. Net new women stay the absolute size test.")
RENT_RATIO_MIN = 1.0
RENT_RATIO_MIN_WHY = ("GROW needs a shop rent no more expensive than the median at its emirate's reference salon sites "
                      "(rent_ratio 1 or more; unknown or the emirate-median fallback passes). Rent only: served women are the demand tests.")
RENT_FALLBACK_MIN = 0.5
RENT_FALLBACK_WHY = ("A cell with no DLD, ADREC or listings rent takes its emirate's median (SHOP_RENT_WHY). When "
                     "half or more of an area's women with a rent live in such cells, the area's women-weighted "
                     "median IS that one emirate-wide number, not an observation of the place: the rent test is "
                     "neutral (passes) and the call low confidence. Lounges: a site cell on the fallback scores "
                     "rent neutral (0.5), low confidence. Nine of the ten Sharjah GROW areas sat at ratio exactly 1.000, "
                     "and manama-ajman / mudayrah-ajman missed at 0.997, on this number alone (2026-10-11). "
                     "Known edge: sharjah-sharjah (15% fallback) keeps its observed-rent call, though its median "
                     "lands on the fallback value (1.000; its listings cells alone give 0.997).")
NEW_SITE_MIN = Rules().grow_min
NEW_SITE_MIN_WHY = ("Quick first cut (2026-10-11): a new lounge here should add at least about what our median "
                    "lounge serves today (~6k women, Huff), net of what it takes from our own lounges.")
WHY = {"NEW_SITE_MIN": NEW_SITE_MIN_WHY, "DEMAND_PCT_MIN": DEMAND_PCT_MIN_WHY,
       "RENT_RATIO_MIN": RENT_RATIO_MIN_WHY, "RENT_FALLBACK_MIN": RENT_FALLBACK_WHY, **WHY}  # shown first on the Decision model page


def _ord(p: float) -> str:
    n = round(p * 100)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def demand_text(where: str, pct: float | None, pct_uae: float | None, emirate: str) -> str:
    """'top 20% of Dubai salon sites on demand · 45th percentile UAE-wide' (the owner's wording)."""
    if pct is None:
        return "demand unknown"
    group = f"{where} salon sites" if where != "UAE" else f"UAE salon sites ({emirate} has under 50)"
    rank = f"top {max(1, round((1 - pct) * 100))}%" if pct >= 0.5 else f"bottom {max(1, round(pct * 100))}%"
    return f"{rank} of {group} on demand · {_ord(pct_uae)} percentile UAE-wide"


def rent_fallback(x) -> bool:
    """The rent is the emirate-median fallback (RENT_FALLBACK_WHY): an area's mostly, a lounge's
    (LoungeFeatures) site cell's."""
    if not isinstance(x, Area):
        return x.site_rent_source == "emirate_median"
    return x.rent_ratio is not None and x.shop_rent_fallback_share >= RENT_FALLBACK_MIN


def rent_ok(a: Area) -> bool:
    """The GROW rent test: no more expensive than its emirate's median salon site; unknown or fallback passes."""
    return a.rent_ratio is None or rent_fallback(a) or a.rent_ratio >= RENT_RATIO_MIN


def rent_text(ratio: float | None, pct_uae: float | None, emirate: str, fallback: bool = False) -> str:
    """'rent ratio 1.25 (cheaper than the median Dubai salon site) · 45th percentile of rent UAE-wide'."""
    if ratio is None:
        return "rent unknown"
    if fallback:
        return f"rent unknown: the {emirate} median shop rent stands in (fallback, not observed), so the rent test is neutral"
    r = f"{ratio:.2f}" if round(ratio, 2) != 1 or ratio == 1 else f"{ratio:.3f}"   # 0.998 is not "1.00"
    side = "cheaper than" if ratio > 1 else "as expensive as" if ratio == 1 else "more expensive than"
    return f"rent ratio {r} ({side} the median {emirate} salon site) · {_ord(pct_uae)} percentile of rent UAE-wide"


def site_text(x) -> str:
    """Both signals in words with their UAE-wide context, for a lounge (LoungeFeatures) or an area."""
    return (f"{demand_text(x.demand_ref, x.demand_pct, x.demand_pct_uae, x.emirate)}; "
            f"{rent_text(x.rent_ratio, x.rent_pct_uae, x.emirate, rent_fallback(x))}")


def classify(a: Area, rules: Rules = Rules()) -> AreaDecision:  # noqa: B008 (frozen)
    """What-if: open a typical lounge here (src/model/served.what_if_open). GROW / WATCH / SKIP on the
    women it would add to the network, its demand percentile and its rent ratio (salon-site reference)."""
    net = a.new_site_net or 0.0
    cheap = rent_ok(a)
    fallback = rent_fallback(a)
    line = rules.grow_min
    strong = a.demand_pct is None or a.demand_pct >= rules.demand_pct_min
    big = net >= line and a.worker_share < WORKER_CAP
    unsat = None if a.premium_reviews_per_1k is None else a.premium_reviews_per_1k < UNSATURATED_PER_1K
    caveats = []
    if a.data_coverage < MIN_COVERAGE:
        caveats.append(f"Only {a.data_coverage:.0%} of its women were searched for competitors: the rest are "
                       "imputed from comparable places in the emirate.")
    if a.rent_ratio is None and a.new_site_net is not None:
        caveats.append("No shop rent here: rent unknown.")
    if fallback and a.new_site_net is not None:
        caveats.append(f"Shop rent is the {a.emirate} median, not observed ({a.shop_rent_fallback_share:.0%} of its "
                       "women are in cells without a rent of their own): the rent test is neutral.")
    if a.demand_ref == "UAE" and a.new_site_net is not None:
        caveats.append(f"{a.emirate} has under 50 reference salon sites: demand is ranked UAE-wide.")
    gap = (net - line) / line
    confidence = "low" if abs(gap) < NEAR_LINE or a.data_coverage < MIN_COVERAGE or (fallback and big) else "high" if abs(gap) >= FAR_LINE else "medium"
    if NON_RESIDENTIAL.search(a.name):
        action, why, confidence = "SKIP", f"Non-residential by name ({a.name}): not where customers live.", "high"
    elif a.women < SKIP_UNDER_WOMEN:
        action, why, confidence = "SKIP", f"Only {a.women:,.0f} women 15+, under the {SKIP_UNDER_WOMEN:,} floor.", "high"
    elif big and cheap and strong:
        action, why = "GROW", f"A new lounge would add about {net:,.0f} women to the network; {site_text(a)}."
    elif big:
        action, why = "WATCH", (f"Enough new women ({net:,.0f}), but "
                                + " and ".join(w for w, bad in (("more expensive than its emirate's median salon site", not cheap),
                                                               ("weaker demand than its emirate's median salon site", not strong)) if bad)
                                + f": {site_text(a)}.")
    elif net >= line:
        action, why = "WATCH", f"Enough new women ({net:,.0f}), but mostly worker housing ({a.worker_share:.0%} of adults)."
    elif net >= line / 2:
        action, why = "WATCH", f"A new lounge would add about {net:,.0f} women: half a typical lounge (GROW needs {line:,})."
    else:
        action, why = "SKIP", f"A new lounge would add only about {net:,.0f} women."
    why += f" Nearest lounge: {a.nearest_lounge_id}, {a.nearest_lounge_km:.1f} km in a straight line."
    return AreaDecision(area_id=a.area_id, action=action, big_enough=big, unsaturated=unsat,
                        rationale=why, caveats=caveats, confidence=confidence)


def classify_all(areas: list[Area], rules: Rules = Rules()) -> list[AreaDecision]:  # noqa: B008 (frozen)
    return [classify(a, rules) for a in areas]
