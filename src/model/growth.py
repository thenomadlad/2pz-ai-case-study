"""Growth areas: GROW / WATCH / SKIP from two questions (every area is already beyond a 15-min
drive of every open lounge, by construction in src/features/lounges.py).

  Big enough?   at least GROW_MIN_WOMEN women 15+, and worker housing under WORKER_CAP of adults.
  Unsaturated?  premium-salon reviews per 1k women (over the cells we searched) under
                UNSATURATED_PER_1K; None when no cell was searched.

  both -> GROW, one -> WATCH (also: big but mostly worker housing), neither -> SKIP; under
  SKIP_UNDER_WOMEN -> SKIP. Unknown saturation, or under MIN_COVERAGE of the women searched,
  caps at WATCH. Thresholds are proposals the user reviews (notebooks/decisions.ipynb).
"""
from src.models import Area, AreaDecision

GROW_MIN_WOMEN = 20_000
SKIP_UNDER_WOMEN = 5_000
WORKER_CAP = 0.5
MIN_COVERAGE = 0.5
UNSATURATED_PER_1K = 50.0

WHY = {
    "GROW_MIN_WOMEN": "Just under the smallest lounge catchment (23k women at medium levels): the least a lounge runs on today.",
    "SKIP_UNDER_WOMEN": "Under 5,000 women an area can't carry a lounge whatever the competition.",
    "WORKER_CAP": "Where most adults live in worker housing, the women estimate rests on the worker-housing female share.",
    "MIN_COVERAGE": "Under half the women in searched cells, the saturation figure describes the minority.",
    "UNSATURATED_PER_1K": (
        "PROPOSAL, pending the user's review. Every lounge catchment with a real premium market "
        "(10+ premium salons) has 88+ premium reviews per 1k women (al-jada 88, median 220); the two "
        "thin ones are 10 and 27. Growth areas of 5k+ women have a median of 5 and a 75th percentile "
        "of 54. 50 is under the least crowded working catchment by a wide margin and splits the "
        "growth areas into the empty majority and the ones with an established premium scene."),
}


def classify(a: Area) -> AreaDecision:
    big = a.women >= GROW_MIN_WOMEN and a.worker_share < WORKER_CAP
    unsat = None if a.premium_reviews_per_1k is None else a.premium_reviews_per_1k < UNSATURATED_PER_1K
    caveats = []
    if unsat is None:
        caveats.append("No competitor data: none of this area's cells were searched, so saturation is unknown.")
    elif a.data_coverage < MIN_COVERAGE:
        caveats.append(f"Competitor data covers only {a.data_coverage:.0%} of the women here.")

    if a.women < SKIP_UNDER_WOMEN:
        action, why = "SKIP", f"Only {a.women:,.0f} women 15+, under the {SKIP_UNDER_WOMEN:,} floor."
    elif big and unsat and a.data_coverage >= MIN_COVERAGE:
        action, why = "GROW", "Big enough and not saturated with premium salons."
    elif big and unsat:
        action, why = "WATCH", "Big enough and looks unsaturated, but too little of it was searched to be sure."
    elif big and unsat is None:
        action, why = "WATCH", "Big enough; saturation unknown (no competitor data)."
    elif big:
        action, why = "WATCH", "Big enough, but already served by premium salons."
    elif a.women >= GROW_MIN_WOMEN:
        action, why = "WATCH", f"Big, but mostly worker housing ({a.worker_share:.0%} of adults)."
    elif unsat:
        action, why = "WATCH", f"Few premium salons, but only {a.women:,.0f} women (GROW needs {GROW_MIN_WOMEN:,})."
    else:
        action, why = "SKIP", f"Under {GROW_MIN_WOMEN:,} women and not clearly unsaturated."
    why += f" Nearest lounge: {a.nearest_lounge_id}, {a.nearest_lounge_km:.1f} km in a straight line."
    return AreaDecision(area_id=a.area_id, action=action, big_enough=big, unsaturated=unsat,
                        rationale=why, caveats=caveats)


def classify_all(areas: list[Area]) -> list[AreaDecision]:
    return [classify(a) for a in areas]
