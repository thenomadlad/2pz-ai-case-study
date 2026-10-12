"""Lounge scorecard: two signals on FIXED scales (site demand, site rent), weighted,
PROTECT / HOLD / SHRINK. Both rank the site within its emirate's frozen market of competitor salon
sites (src/features/lounges.SITE_REFERENCE_WHY), never against our own lounges. Both score the SITE (a typical lounge there), as growth areas do; the
lounge's own served women are context (performance_vs_site), not scored.

Fixed scales so a lounge's score doesn't move when a sibling opens or closes. Each `why` says how its
anchors were set (2026-10-11, served-demand model). Capture and rating are shown, not scored;
cannibalisation is a what-if on the lounge page, not a signal. Affluence weighting is off at baseline
(Levels.affluence = "low", elasticity 0: notebooks/features/affluence.ipynb); it stays one of the four
assumption axes the flip count varies.
"""
from collections import Counter
from dataclasses import dataclass, fields
from itertools import product

from src.models import Decision, Levels, LoungeFeatures


@dataclass(frozen=True)
class Signal:
    name: str
    field: str
    label: str
    worst: float  # value that scores 0
    best: float   # value that scores 1
    why: str
    weight: float = 1.0


RENT_RATIO_P10 = 0.6176   # RENT_RATIO_WHY
RENT_RATIO_P90 = 1.4290
RENT_RATIO_WHY = (
    "Frozen 2026-10-11 from the reference salon sites (scripts/build_site_reference.py): the 10th and "
    "90th percentiles of rent_ratio over all 1,123, each against its own emirate's median. A site as "
    "dear, relative to its emirate's salon sites, as the dearest tenth scores 0; as cheap as the "
    "cheapest tenth scores 1; the emirate's median salon site (ratio 1) scores about 0.47.")

SIGNALS: tuple[Signal, ...] = (
    Signal("demand", "demand_pct", "Site demand: share of its emirate's salon sites it out-serves",
           0, 1,
           "Scores the SITE, not the lounge's popularity: the women a typical lounge (median reviews and "
           "rating) would serve there, this lounge closed and rivals and siblings open, ranked among the "
           "frozen reference of competitor salon sites in the same emirate (each with a typical lounge "
           "there and all our lounges open; UAE-wide where an emirate has under 50: SITE_REFERENCE_WHY "
           "in src/features/lounges.py). The 0..1 percentile is the score. The lounge's own served "
           "women are shown as performance_vs_site (context, not scored): served by its own reviews, "
           "they partly restate review volume (SANITY_CHECKS F2)."),
    Signal("cost", "rent_ratio", "Site rent: emirate median shop rent at salon sites ÷ this site's",
           RENT_RATIO_P10, RENT_RATIO_P90,
           "Above 1 = cheaper than a typical salon site in its emirate. Scale frozen (RENT_RATIO_WHY). "
           "Rent only: served women are already the demand signal, so they are not counted twice. Site "
           "shop rent from DLD, ADREC, listings or the emirate median; a missing rent scores neutral. "
           "Cannibalisation is not scored: it is a what-if shown on the lounge page."),
)

PROTECT_AT = 0.65
SHRINK_AT = 0.35
THRESHOLDS_WHY = (
    f"PROTECT at a composite of {PROTECT_AT} or more means the lounge clears the bar on most "
    f"signals, not just one. SHRINK at {SHRINK_AT} or less means it is weak on most signals. "
    "Everything between is HOLD: with no revenue or lease data, strong calls need the signals to agree."
)
AXES = tuple(f.name for f in fields(Levels))     # travel, coverage, worker_share, affluence
COMBOS = 3 ** len(AXES)                          # 81 level combinations
FLIP_LOW_SHARE = 1 / 3   # of the combinations: a call that flips this often is low confidence
FLIP_LOW = round(FLIP_LOW_SHARE * COMBOS)        # 27 of 81
FLIP_WHY = (f"A lounge whose action changes in {FLIP_LOW} or more (a third) of the {COMBOS} "
            "combinations of travel time, competitor coverage, worker-housing share and affluence "
            "weighting depends on the assumptions more than on the data, so its call is low confidence.")
NEUTRAL = 0.5  # a missing rating gap never scores as the worst; thin-market capture is pulled toward it
THIN_MARKET = 10
THIN_MARKET_WHY = ("Under 10 premium salons, capture is a share of a tiny pool, so it is noisy: its score keeps "
                   "only premium_pool / 10 of its distance from neutral (0 salons: neutral). A blend replaces "
                   "the old cliff, where three 5-review salons swung al-dhafra by 0.14 (SANITY_CHECKS SC4). "
                   "A thin market stays a low-confidence reason.")
WEIGHT_STEPS = (0.75, 1.25)
WEIGHT_WHY = ("The weights are a design choice, not data. Each signal's weight is moved ×0.75 and ×1.25, "
              "one at a time (8 variants); a call that changes under any of them depends on the weighting, "
              "so it is low confidence. The decision lines aren't varied: within 0.05 of one is already low.")
NO_FINANCIALS = ("No revenue, lease or footfall data: site cost is an area shop rent (150 m² assumed) plus assumed fit-out, "
                 "so this scores location, market and rent, not return on invested capital.")


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


def _action(composite: float) -> str:
    return "PROTECT" if composite >= PROTECT_AT else "SHRINK" if composite <= SHRINK_AT else "HOLD"


def _composite(scores: dict[str, float], weights: dict[str, float]) -> float:
    return sum(weights[n] * scores[n] for n in weights) / sum(weights.values())


def weight_flips(scores: dict[str, float]) -> list[str]:
    """The weight variants (each signal ×0.75 or ×1.25, one at a time) that change the call."""
    base = {s.name: s.weight for s in SIGNALS}
    action = _action(_composite(scores, base))
    out = []
    for s in SIGNALS:
        for step in WEIGHT_STEPS:
            new = _action(_composite(scores, {**base, s.name: s.weight * step}))
            if new != action:
                out.append(f"{s.name} weight ×{step:g} → {new}")
    return out


def _decide(f: LoungeFeatures, flips: int | None) -> Decision:
    if f.not_scored:
        return Decision(branch_id=f.branch_id, action="NOT SCORED", confidence="low",
                        rationale="Not scored: this lounge serves travellers, not the women in its catchment.",
                        key_drivers=[], caveats=[])
    scores = {s.name: score(s, getattr(f, s.field)) for s in SIGNALS}
    composite = _composite(scores, {s.name: s.weight for s in SIGNALS})
    action = _action(composite)
    caveats = [NO_FINANCIALS]
    flippy = flips is not None and flips >= FLIP_LOW
    if flippy:
        caveats.append(f"The call changes in {flips} of {COMBOS} assumption combinations.")
    wflips = weight_flips(scores)
    if wflips:
        caveats.append("The call depends on the signal weights: it changes with " + "; ".join(wflips) + ".")
    return Decision(
        branch_id=f.branch_id, action=action, weight_flips=wflips,
        confidence=_confidence(composite, flippy or bool(wflips)),
        rationale=(f"Composite {composite:.2f} across site demand and site rent "
                   f"(PROTECT ≥ {PROTECT_AT}, SHRINK ≤ {SHRINK_AT})."),
        key_drivers=sorted(scores, key=lambda n: abs(scores[n] - NEUTRAL), reverse=True)[:2],
        caveats=caveats, composite=round(composite, 4), scores={k: round(v, 4) for k, v in scores.items()})


def decide(features: list[LoungeFeatures], flips: dict[str, int] | None = None) -> list[Decision]:
    """`flips`: per lounge, how many of the 81 level combinations change its action (level_flips)."""
    return [_decide(f, (flips or {}).get(f.branch_id)) for f in features]


def level_flips(v3, assumptions, levels, closed=frozenset()) -> dict[str, int]:
    """How many of the 81 level combinations give each lounge a different action than `levels`."""
    from src.features.lounges import build  # here, not at the top: build doesn't need the scorecard

    def actions(lv):
        return {d.branch_id: d.action for d in decide(build(v3, assumptions, lv, closed, areas=False)[0])}

    base = actions(levels)
    out = Counter()
    for lv in product(("low", "medium", "high"), repeat=len(AXES)):
        for b, a in actions(Levels(*lv)).items():
            out[b] += a != base[b]
    return {b: out[b] for b in base}


def counts(decisions: list[Decision]) -> dict[str, int]:
    """PROTECT / HOLD / SHRINK counts; NOT SCORED lounges are left out."""
    c = Counter(d.action for d in decisions)
    return {a: c[a] for a in ("PROTECT", "HOLD", "SHRINK")}
