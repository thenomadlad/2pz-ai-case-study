import json
import statistics

from src.config import Settings
from src.config import settings as default_settings
from src.features.assign import assign_communities, haversine_km
from src.models import Branch, BranchFeatures, Community, NetworkStats


def _percentiles(values: list[float]) -> tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    ordered = sorted(values)
    return (statistics.median(ordered), _percentile(ordered, 0.25), _percentile(ordered, 0.75))


def _percentile(ordered: list[float], pct: float) -> float:
    if len(ordered) == 1:
        return ordered[0]
    k = pct * (len(ordered) - 1)
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    frac = k - lo
    return ordered[lo] + (ordered[hi] - ordered[lo]) * frac


def build_features(
    branches: list[Branch], communities: list[Community],
    price_flags: list[str], contest_ratio: float,
) -> tuple[list[BranchFeatures], NetworkStats, list]:
    assignments = assign_communities(branches, communities, contest_ratio)
    price_flag_set = set(price_flags)
    community_by_id = {c.id: c for c in communities}

    median_price = statistics.median([b.avg_price_aed for b in branches if b.avg_price_aed])

    features: list[BranchFeatures] = []
    for branch in branches:
        served = [a for a in assignments if a.nearest_branch_id == branch.id]
        female_pop_served = sum(a.female_pop for a in served)
        contested_pop = sum(a.female_pop for a in served if a.contested)

        if served:
            mean_distance = (
                sum(a.nearest_km * a.female_pop for a in served) / female_pop_served
                if female_pop_served else sum(a.nearest_km for a in served) / len(served)
            )
            max_distance = max(a.nearest_km for a in served)
        else:
            mean_distance, max_distance = 0.0, 0.0

        siblings = [b for b in branches if b.id != branch.id]
        sibling_distances = [haversine_km(branch.lat, branch.lng, s.lat, s.lng) for s in siblings]
        nearest_sibling_km = min(sibling_distances) if sibling_distances else 0.0
        siblings_within_5km = sum(1 for d in sibling_distances if d <= 5.0)

        estimated_fields = ["avg_price_aed"] if branch.id in price_flag_set else []
        if any(community_by_id[a.community_id].is_estimated for a in served
               if a.community_id in community_by_id):
            estimated_fields.append("female_pop_served")

        features.append(BranchFeatures(
            branch_id=branch.id,
            name=branch.name,
            lat=branch.lat,
            lng=branch.lng,
            female_pop_served=female_pop_served,
            communities_served=len(served),
            mean_distance_km=mean_distance,
            max_distance_km=max_distance,
            contested_pop=contested_pop,
            contested_share=(contested_pop / female_pop_served) if female_pop_served else 0.0,
            nearest_sibling_km=nearest_sibling_km,
            siblings_within_5km=siblings_within_5km,
            avg_price_aed=branch.avg_price_aed or median_price,
            price_index=(branch.avg_price_aed or median_price) / median_price,
            rating=branch.rating,
            review_count=branch.review_count,
            pop_per_1k_rank=0,
            estimated_fields=estimated_fields,
        ))

    ranked = sorted(features, key=lambda f: f.female_pop_served, reverse=True)
    for rank, f in enumerate(ranked, start=1):
        f.pop_per_1k_rank = rank

    pop_med, pop_p25, pop_p75 = _percentiles([f.female_pop_served for f in features])
    contest_med, contest_p25, contest_p75 = _percentiles([f.contested_share for f in features])
    price_med, price_p25, price_p75 = _percentiles([f.avg_price_aed for f in features])
    ratings = [f.rating for f in features if f.rating is not None]
    if ratings:
        rating_med, rating_p25, rating_p75 = _percentiles(ratings)
    else:
        rating_med = rating_p25 = rating_p75 = None

    network = NetworkStats(
        branch_count=len(features),
        total_female_population=sum(f.female_pop_served for f in features),
        female_pop_served_median=pop_med,
        female_pop_served_p25=pop_p25,
        female_pop_served_p75=pop_p75,
        contested_share_median=contest_med,
        contested_share_p25=contest_p25,
        contested_share_p75=contest_p75,
        avg_price_aed_median=price_med,
        avg_price_aed_p25=price_p25,
        avg_price_aed_p75=price_p75,
        rating_median=rating_med,
        rating_p25=rating_p25,
        rating_p75=rating_p75,
    )
    return features, network, assignments


def main(settings: Settings | None = None) -> None:
    settings = settings or default_settings
    settings.processed_dir.mkdir(parents=True, exist_ok=True)

    branches = [Branch(**b) for b in json.loads((settings.raw_dir / "branches.json").read_text())]
    price_flags = json.loads((settings.raw_dir / "price_flags.json").read_text())
    communities = [Community(**c) for c in
                   json.loads((settings.raw_dir / "communities.json").read_text())]

    features, network, assignments = build_features(branches, communities, price_flags, settings.contest_ratio)

    (settings.processed_dir / "branch_features.json").write_text(json.dumps({
        "network": network.model_dump(),
        "branches": [f.model_dump() for f in features],
    }, indent=2))
    (settings.processed_dir / "community_assignment.json").write_text(
        json.dumps([a.model_dump() for a in assignments], indent=2))
    (settings.processed_dir / "communities.json").write_text(
        json.dumps([c.model_dump() for c in communities], indent=2))

    print(f"features: wrote {len(features)} branch features, {len(assignments)} community "
          f"assignments")


if __name__ == "__main__":
    main()
