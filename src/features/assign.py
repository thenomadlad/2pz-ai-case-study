import math

from src.models import Branch, Community, CommunityAssignment, Competitor

EARTH_RADIUS_KM = 6371.0
# A competitor further than this from every seeded community centroid is dropped rather
# than lumped into an edge community: the 50 seeded communities don't tile all of Dubai.
# ponytail: centroid distance, not community polygons; use polygons if counts look off.
COMPETITOR_MAX_KM = 3.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def assign_communities(
    branches: list[Branch], communities: list[Community], contest_ratio: float,
) -> list[CommunityAssignment]:
    assignments: list[CommunityAssignment] = []
    for community in communities:
        distances = sorted(
            ((haversine_km(community.lat, community.lng, b.lat, b.lng), b.id) for b in branches),
            key=lambda pair: pair[0],
        )
        nearest_km, nearest_id = distances[0]
        if len(distances) > 1:
            second_km, second_id = distances[1]
            if nearest_km > 0:
                contested = (second_km / nearest_km) < contest_ratio
            else:
                contested = (second_km == 0)
        else:
            second_km, second_id, contested = None, None, False

        assignments.append(CommunityAssignment(
            community_id=community.id,
            nearest_branch_id=nearest_id,
            nearest_km=nearest_km,
            second_branch_id=second_id,
            second_km=second_km,
            contested=contested,
            female_pop=community.population_female or 0,
        ))
    return assignments


def competitor_community(
    competitors: list[Competitor], communities: list[Community],
    max_km: float = COMPETITOR_MAX_KM,
) -> dict[str, str]:
    """Competitor id -> the community it counts toward: its nearest, if within max_km."""
    result = {}
    for k in competitors if communities else []:
        km, community_id = min((haversine_km(k.lat, k.lng, c.lat, c.lng), c.id)
                               for c in communities)
        if km <= max_km:
            result[k.id] = community_id
    return result


def count_competitors(
    competitors: list[Competitor], communities: list[Community],
    max_km: float = COMPETITOR_MAX_KM,
) -> dict[str, int]:
    """Competitors per community: each competitor counts toward its nearest community."""
    counts = {c.id: 0 for c in communities}
    for community_id in competitor_community(competitors, communities, max_km).values():
        counts[community_id] += 1
    return counts
