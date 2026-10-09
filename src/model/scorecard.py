"""Lounge scorecard: four signals on FIXED scales, weighted, PROTECT / HOLD / SHRINK.

Fixed scales so a lounge's score doesn't move when a sibling opens or closes. Anchors were set
from the v3 features at medium levels (notebooks/decisions.ipynb); each `why` says why. They
were reviewed by the user on 2026-10-09 (rating at half weight; flips lower confidence).
"""
from collections import Counter
from dataclasses import dataclass
from itertools import product

from src.models import Decision, LoungeFeatures


@dataclass(frozen=True)
class Signal:
    name: str
    field: str
    label: str
    worst: float  # value that scores 0
    best: float   # value that scores 1
    why: str
    weight: float = 1.0


SIGNALS: tuple[Signal, ...] = (
    Signal("demand", "catchment_women", "Women 15+ in the 15-min catchment", 0, 200_000,
           "Lounges range 23k-272k women, median 105k; 200k is where the four big Dubai lounges "
           "sit, and one lounge can't absorb more, so extra women stop counting."),
    Signal("cannibalisation", "shared_share", "Share of catchment women another lounge also reaches",
           1.0, 0.0,
           "Already a 0-100% share: 0% means no sibling reaches this lounge's women. Abu Dhabi "
           "city lounges sit at 85-100%."),
    Signal("capture", "capture", "Lounge reviews as a share of lounge + premium substitutes", 0, 0.15,
           "Median 6.5% over the scored lounges; 15% is about the best reliable lounge (al-taif-mall, 14%). Thin premium "
           "markets (under 10 premium salons) score 0.5: a share of a tiny pool is noise."),
    Signal("rating", "rating_gap", "Rating minus the substitutes' median rating (stars)", -0.3, 0.3,
           "Gaps run -0.2 to +0.3, median -0.1: most lounges rate slightly below their premium "
           "substitutes; ±0.3 stars covers the whole range. Half weight: Google ratings come in "
           "0.1 steps, so the gap takes only six values.", 0.5),
)

PROTECT_AT = 0.65
SHRINK_AT = 0.35
THRESHOLDS_WHY = (
    f"PROTECT at a composite of {PROTECT_AT} or more means the lounge clears the bar on most "
    f"signals, not just one. SHRINK at {SHRINK_AT} or less means it is weak on most signals. "
    "Everything between is HOLD: with no revenue or rent data, strong calls need the signals to agree."
)
FLIP_LOW = 9  # of the 27 level combinations: a call that flips this often is low confidence
FLIP_WHY = (f"A lounge whose action changes in {FLIP_LOW} or more of the 27 combinations of travel "
            "time, competitor coverage and worker-housing share depends on the assumptions more "
            "than on the data, so its call is low confidence.")
NEUTRAL = 0.5  # a missing rating gap, or capture in a thin market, never scores as the worst
NO_FINANCIALS = ("No revenue, rent or footfall data: this scores location and market position "
                 "only, not return on invested capital.")


def score(signal: Signal, value: float | None) -> float:
    if value is None:
        return NEUTRAL
    return max(0.0, min(1.0, (value - signal.worst) / (signal.best - signal.worst)))


LOW_MARGIN = 0.05   # composite this close to a line: low confidence
HIGH_MARGIN = 0.10  # this far from both lines: high confidence


def _confidence(composite: float, low: bool) -> str:
    margin = min(abs(composite - PROTECT_AT), abs(composite - SHRINK_AT))
    if low or margin < LOW_MARGIN:
        return "low"
    return "high" if margin >= HIGH_MARGIN else "medium"


def _decide(f: LoungeFeatures, flips: int | None) -> Decision:
    if f.not_scored:
        return Decision(branch_id=f.branch_id, action="NOT SCORED", confidence="low",
                        rationale="Not scored: this lounge serves travellers, not the women in its catchment.",
                        key_drivers=[], caveats=[])
    scores = {s.name: score(s, getattr(f, s.field)) for s in SIGNALS}
    if f.thin_premium_market:
        scores["capture"] = NEUTRAL
    composite = sum(s.weight * scores[s.name] for s in SIGNALS) / sum(s.weight for s in SIGNALS)
    action = "PROTECT" if composite >= PROTECT_AT else "SHRINK" if composite <= SHRINK_AT else "HOLD"
    caveats = [NO_FINANCIALS]
    if f.thin_premium_market:
        caveats.append(f"Thin premium market ({f.premium_pool} premium salons): capture scored neutral.")
    if f.rating_gap is None:
        caveats.append("No rating gap (missing rating or no rated substitutes): scored neutral.")
    flippy = flips is not None and flips >= FLIP_LOW
    if flippy:
        caveats.append(f"The call changes in {flips} of 27 assumption combinations.")
    return Decision(
        branch_id=f.branch_id, action=action,
        confidence=_confidence(composite, f.thin_premium_market or f.rating_gap is None or flippy),
        rationale=(f"Composite {composite:.2f} across demand, cannibalisation, capture and rating "
                   f"(PROTECT ≥ {PROTECT_AT}, SHRINK ≤ {SHRINK_AT})."),
        key_drivers=sorted(scores, key=lambda n: abs(scores[n] - NEUTRAL), reverse=True)[:2],
        caveats=caveats, composite=round(composite, 4), scores={k: round(v, 4) for k, v in scores.items()})


def decide(features: list[LoungeFeatures], flips: dict[str, int] | None = None) -> list[Decision]:
    """`flips`: per lounge, how many of the 27 level combinations change its action (level_flips)."""
    return [_decide(f, (flips or {}).get(f.branch_id)) for f in features]


def level_flips(v3, assumptions, levels, closed=frozenset()) -> dict[str, int]:
    """How many of the 27 level combinations give each lounge a different action than `levels`."""
    from src.features.lounges import build  # here, not at the top: build doesn't need the scorecard
    from src.models import Levels

    def actions(lv):
        return {d.branch_id: d.action for d in decide(build(v3, assumptions, lv, closed)[0])}

    base = actions(levels)
    out = Counter()
    for lv in product(("low", "medium", "high"), repeat=3):
        for b, a in actions(Levels(*lv)).items():
            out[b] += a != base[b]
    return {b: out[b] for b in base}


def counts(decisions: list[Decision]) -> dict[str, int]:
    """PROTECT / HOLD / SHRINK counts; NOT SCORED lounges are left out."""
    c = Counter(d.action for d in decisions)
    return {a: c[a] for a in ("PROTECT", "HOLD", "SHRINK")}
