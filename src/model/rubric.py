"""Branch rubric: four signals on FIXED scales, equal-weighted, absolute thresholds.

Fixed scales (not min-max across the network) so a branch's score doesn't move just
because a sibling opened or closed, and so a network that is healthy everywhere can
come out with zero SHRINKs. Anchors were picked from the Dubai data distribution
(see each `why`); they are assumptions, and the app shows them next to every decision.
"""
from dataclasses import dataclass

from src.models import BranchFeatures, Decision, NetworkStats


@dataclass(frozen=True)
class Signal:
    name: str
    field: str
    label: str
    worst: float  # value that scores 0
    best: float   # value that scores 1
    why: str


SIGNALS: tuple[Signal, ...] = (
    Signal("demand", "female_pop_served", "Female residents in catchment", 0, 150_000,
           "150k is roughly what the busiest Dubai branches serve; beyond that a single "
           "branch can't absorb more demand, so extra population stops counting."),
    Signal("cannibalisation", "contested_share", "Share of catchment contested by a sibling",
           1.0, 0.0,
           "A share, so it is already on a fixed 0-100% scale: 0% means no sibling competes "
           "for this branch's communities."),
    Signal("competition", "competitors_per_10k", "Competitor salons per 10k female residents",
           15.0, 0.0,
           "Dubai communities run a median of ~5 and a 75th percentile of ~11 competitors per "
           "10k female residents (OSM); 15 marks a clearly saturated catchment."),
    Signal("quality", "rating", "Customer rating (stars)", 4.0, 5.0,
           "Salon ratings cluster above 4; below 4.0 is a genuine warning sign, so 4.0-5.0 is "
           "the range that discriminates."),
)

PROTECT_AT = 0.65
SHRINK_AT = 0.35
THRESHOLDS_WHY = (
    f"PROTECT at a composite of {PROTECT_AT} or more means the branch clears the bar on "
    f"most signals, not just one. SHRINK at {SHRINK_AT} or less means it is weak on most "
    "signals. Everything between is HOLD. The middle band is deliberately wide: with no "
    "revenue or rent data, the model should only make strong calls when the signals agree."
)
MISSING_SCORE = 0.5  # a missing rating is scored neutral, never as the worst


def score(signal: Signal, value: float | None) -> float:
    if value is None:
        return MISSING_SCORE
    return max(0.0, min(1.0, (value - signal.worst) / (signal.best - signal.worst)))


def _confidence(composite: float, missing: list[str]) -> str:
    margin = min(abs(composite - PROTECT_AT), abs(composite - SHRINK_AT))
    if missing or margin < 0.05:
        return "low"
    return "high" if margin >= 0.10 else "medium"


class RubricModel:
    name = "rubric"

    def decide(self, branches: list[BranchFeatures], network: NetworkStats) -> list[Decision]:
        decisions = []
        for b in branches:
            values = {s.name: getattr(b, s.field) for s in SIGNALS}
            scores = {name: score(s, values[name]) for name, s in zip(values, SIGNALS)}
            composite = sum(scores.values()) / len(scores)
            missing = [s.label for s in SIGNALS if values[s.name] is None]

            if composite >= PROTECT_AT:
                action = "PROTECT"
            elif composite <= SHRINK_AT:
                action = "SHRINK"
            else:
                action = "HOLD"

            # Drivers are the signals pulling hardest away from neutral.
            key_drivers = sorted(scores, key=lambda n: abs(scores[n] - 0.5), reverse=True)[:2]
            caveats = [("No revenue, rent or footfall data: this scores location and market "
                        "position only, not return on invested capital.")]
            if missing:
                caveats.append(f"Missing input scored as neutral: {', '.join(missing)}.")

            decisions.append(Decision(
                branch_id=b.branch_id, action=action,
                confidence=_confidence(composite, missing),
                rationale=(f"Composite {composite:.2f} across demand, cannibalisation, "
                           f"competition and quality (PROTECT ≥ {PROTECT_AT}, "
                           f"SHRINK ≤ {SHRINK_AT})."),
                key_drivers=key_drivers, caveats=caveats,
                composite=round(composite, 4),
                scores={k: round(v, 4) for k, v in scores.items()},
            ))
        return decisions
