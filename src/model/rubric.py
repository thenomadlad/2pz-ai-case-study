from src.models import BranchFeatures, Decision, NetworkStats

FEATURE_NAMES = ("female_pop_served", "contested_share", "rating")


def _normalize(value: float, lo: float, hi: float) -> float:
    if hi == lo:
        return 0.5
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


class RubricModel:
    name = "rubric"

    def decide(self, branches: list[BranchFeatures], network: NetworkStats) -> list[Decision]:
        if not branches:
            return []

        pops = [b.female_pop_served for b in branches]
        contested = [b.contested_share for b in branches]
        ratings = [b.rating for b in branches if b.rating is not None]
        rating_fallback = network.rating_median if network.rating_median is not None else 4.0

        pop_lo, pop_hi = min(pops), max(pops)
        contest_lo, contest_hi = min(contested), max(contested)
        rating_lo, rating_hi = (min(ratings), max(ratings)) if ratings else (rating_fallback,
                                                                              rating_fallback)

        scored = []
        for b in branches:
            pop_score = _normalize(b.female_pop_served, pop_lo, pop_hi)
            contest_score = 1 - _normalize(b.contested_share, contest_lo, contest_hi)
            rating_value = b.rating if b.rating is not None else rating_fallback
            rating_score = _normalize(rating_value, rating_lo, rating_hi)
            composite = (pop_score + contest_score + rating_score) / 3
            scored.append((composite, b))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        n = len(scored)
        top_third = max(1, n // 3)
        bottom_third = max(1, n // 3)

        decisions = []
        for i, (composite, b) in enumerate(scored):
            if i < top_third:
                action = "PROTECT"
            elif i >= n - bottom_third:
                action = "SHRINK"
            else:
                action = "HOLD"

            # Normalize each feature's deviation by its network IQR (p75-p25) before comparing,
            # so features on very different scales (e.g. female_pop_served in the thousands vs.
            # contested_share/rating in [0,1]-ish ranges) can be fairly ranked against each
            # other. Without this, female_pop_served would dominate "key drivers" essentially
            # every time regardless of whether it's actually the standout feature.
            eps = 1e-9
            pop_iqr = network.female_pop_served_p75 - network.female_pop_served_p25
            contest_iqr = network.contested_share_p75 - network.contested_share_p25
            deviations = {
                "female_pop_served": abs(b.female_pop_served - network.female_pop_served_median)
                                      / (pop_iqr + eps),
                "contested_share": abs(b.contested_share - network.contested_share_median)
                                    / (contest_iqr + eps),
            }
            if network.rating_median is not None and b.rating is not None:
                rating_iqr = (network.rating_p75 or 0) - (network.rating_p25 or 0)
                deviations["rating"] = abs(b.rating - network.rating_median) / (rating_iqr + eps)
            key_drivers = sorted(deviations, key=deviations.get, reverse=True)[:2]

            decisions.append(Decision(
                branch_id=b.branch_id,
                action=action,
                confidence="medium",
                rationale=(f"Composite rubric score {composite:.2f} on population, contest "
                           f"share, and rating places this branch in the {action.lower()} "
                           f"tier of the network."),
                key_drivers=key_drivers,
                caveats=[("Linear rubric over 3 features only; no revenue, footfall, or "
                          "competitor context.")],
            ))
        return decisions
