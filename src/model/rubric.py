from src.models import BranchFeatures, Decision, NetworkStats

FEATURE_NAMES = ("female_pop_served", "contested_share", "rating")


def _normalize(value: float, lo: float, hi: float) -> float:
    if hi == lo:
        return 0.5
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


class RubricModel:
    name = "rubric"

    def decide(self, branches: list[BranchFeatures], network: NetworkStats) -> list[Decision]:
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

            deviations = {
                "female_pop_served": abs(b.female_pop_served - network.female_pop_served_median),
                "contested_share": abs(b.contested_share - network.contested_share_median),
            }
            if network.rating_median is not None and b.rating is not None:
                deviations["rating"] = abs(b.rating - network.rating_median)
            key_drivers = sorted(deviations, key=deviations.get, reverse=True)[:2]

            decisions.append(Decision(
                branch_id=b.branch_id,
                action=action,
                confidence="medium",
                rationale=(f"Composite rubric score {composite:.2f} on population, contest "
                           f"share, and rating places this branch in the {action.lower()} "
                           f"tier of the network."),
                key_drivers=key_drivers,
                caveats=["Linear rubric over 3 features only; no revenue, footfall, or "
                         "competitor context."],
            ))
        return decisions
