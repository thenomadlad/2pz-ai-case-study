"""Opportunity areas: every community gets GROW / WATCH / SKIP from a two-question 2x2.

  Underserved?  nearest Bedashing branch is more than FAR_KM away.
  Unsaturated?  fewer than UNSATURATED_PER_10K competitor salons per 10k female residents.

  both -> GROW, exactly one -> WATCH, neither -> SKIP. Communities below MIN_POP, or that
  already host a branch, are SKIP regardless. Industrial / worker-housing communities are
  capped at WATCH: the uniform female-share estimate is known to overstate their demand.
"""
import re

from src.models import CommunityFeatures, OpportunityDecision

FAR_KM = 5.0
UNSATURATED_PER_10K = 5.0
MIN_POP = 20_000
# ponytail: name heuristic for worker-housing areas; replace with real per-community
# gender split if Dubai Statistics Center ever publishes one.
WORKER_HOUSING = re.compile(r"industrial|investment park", re.IGNORECASE)

THRESHOLDS_WHY = (
    f"Underserved means the nearest Bedashing branch is over {FAR_KM:g} km away, about the "
    "median for a Dubai community today, so these are the less-covered half of the city. "
    f"Unsaturated means fewer than {UNSATURATED_PER_10K:g} competitor salons per 10k female "
    "residents, about the Dubai median. Areas under "
    f"{MIN_POP:,} estimated female residents (roughly the median community) are too small "
    "to carry a branch on their own."
)


def classify(c: CommunityFeatures) -> OpportunityDecision:
    underserved = c.nearest_branch_km > FAR_KM
    unsaturated = c.competitors_per_10k < UNSATURATED_PER_10K
    caveats = [("Competitor counts come from OpenStreetMap and are a lower bound, so "
                "saturation may be understated.")]

    if c.hosts_branch:
        action, why = "SKIP", "Already hosts a Bedashing branch."
    elif c.female_pop < MIN_POP:
        action, why = "SKIP", (f"Only {c.female_pop:,} estimated female residents, below the "
                               f"{MIN_POP:,} floor.")
    elif underserved and unsaturated:
        action, why = "GROW", "Underserved by Bedashing and not saturated with competitors."
    elif underserved:
        action, why = "WATCH", "Underserved by Bedashing, but already crowded with competitors."
    elif unsaturated:
        action, why = "WATCH", "Few competitors, but already within reach of a Bedashing branch."
    else:
        action, why = "SKIP", "Within reach of a Bedashing branch and crowded with competitors."

    if action == "GROW" and WORKER_HOUSING.search(c.name):
        action = "WATCH"
        why += " Capped at WATCH: likely worker housing, where demand is overstated."
        caveats.append("Female population here is a uniform 49% estimate; worker-housing "
                       "areas are mostly male, so real demand is likely far lower.")

    why += f" Nearest branch: {c.nearest_branch_id}, {c.nearest_branch_km:.1f} km."
    return OpportunityDecision(community_id=c.community_id, action=action,
                               underserved=underserved, unsaturated=unsaturated,
                               rationale=why, caveats=caveats)


def classify_all(communities: list[CommunityFeatures]) -> list[OpportunityDecision]:
    return [classify(c) for c in communities]
