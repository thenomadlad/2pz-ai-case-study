"""Lounge scorecard: two signals on FIXED scales (site demand, site rent), weighted,
PROTECT / HOLD / SHRINK. Both rank the site within its emirate's frozen market of competitor salon
sites (src/features/lounges.SITE_REFERENCE_WHY), never against our own lounges. Both score the SITE (a typical lounge there), as growth areas do; the
lounge's own served women are context (performance_vs_site), not scored.

Fixed scales so a lounge's score doesn't move when a sibling opens or closes. Each `why` says how its
anchors were set (2026-10-11, served-demand model). Capture and rating are shown, not scored;
cannibalisation is a what-if on the lounge page, not a signal. Affluence weighting is off at baseline
(Levels.affluence = "low", elasticity 0: notebooks/features/affluence.ipynb). The flip count varies only
LIVE_AXES (LIVE_AXES_WHY).
"""
from collections import Counter
from dataclasses import dataclass, replace
from itertools import product

from src.model.growth import rent_fallback
from src.models import Decision, LoungeFeatures, Rules


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
    "90th percentiles of rent_ratio (its emirate's median salon-site rent ÷ its own) over all 1,123. "
    f"A ratio of {RENT_RATIO_P10:.2f} or less (rent {1 / RENT_RATIO_P10:.1f}x the emirate median or more: the "
    f"most expensive 10% of salon sites) scores 0; {RENT_RATIO_P90:.2f} or more (rent {1 / RENT_RATIO_P90:.0%} of the "
    "median or less: the cheapest 10%) scores 1; in between it scales evenly, so a site at its emirate's "
    f"median rent scores {(1 - RENT_RATIO_P10) / (RENT_RATIO_P90 - RENT_RATIO_P10):.2f}.")

SIGNALS: tuple[Signal, ...] = (
    Signal("demand", "demand_pct", "Site demand: share of its emirate's salon sites it out-serves",
           0, 1,
           "Scores the SITE, not how much the lounge itself sells: the women a typical lounge (frozen at 757 reviews, "
           "4.6★: TYPICAL_WHY in src/features/lounges.py) would serve there, this lounge closed and rivals and siblings open, ranked among the "
           "frozen reference of competitor salon sites in the same emirate (each with a typical lounge "
           "there and all our lounges open; UAE-wide where an emirate has under 50: SITE_REFERENCE_WHY "
           "in src/features/lounges.py). The 0..1 percentile is the score. The lounge's own served "
           "women are shown as performance_vs_site (context, not scored): served by its own reviews, "
           "they partly restate review volume (docs/sanity-checks.md F2)."),
    Signal("cost", "rent_ratio", "Site rent: emirate median shop rent at salon sites ÷ this site's",
           RENT_RATIO_P10, RENT_RATIO_P90,
           "Above 1 = cheaper than a typical salon site in its emirate. Scale frozen (RENT_RATIO_WHY). "
           "Rent only: served women are already the demand signal, so they are not counted twice. Site "
           "shop rent from DLD, ADREC or listings; a missing rent scores neutral. "
           "A site cell on the emirate-median fallback scores neutral too (growth.RENT_FALLBACK_WHY). "
           "Cannibalisation is not scored: it is a what-if shown on the lounge page."),
)

RULES = Rules()          # the baseline's decision rules; a what-if passes its own
PROTECT_AT = RULES.protect_at
SHRINK_AT = RULES.shrink_at
THRESHOLDS_WHY = (
    f"PROTECT at a composite of {PROTECT_AT} or more, SHRINK at {SHRINK_AT} or less: {PROTECT_AT - 0.5:.2f} "
    "either side of a neutral 0.5. With two equal signals, even a perfect score on one needs at least "
    f"{2 * PROTECT_AT - 1:.1f} on the other to reach PROTECT (and a zero on one needs {2 * SHRINK_AT:.1f} on the other "
    "to escape SHRINK): the two have to broadly agree. Everything between is HOLD: with no revenue or lease "
    "data, a strong call needs both signals behind it."
)
LIVE_AXES = ("travel", "coverage", "worker_share")   # LIVE_AXES_WHY
LIVE_AXES_WHY = ("Only the assumptions that reach the scoring are varied: drive time (the decay across the 10/15/20-min "
                 "bands), competitor coverage (the competitors' pull) and worker-housing share (src/model/served.LEVELS_WHY). "
                 "Affluence weighting is off, so it stays at baseline.")
COMBOS = 3 ** len(LIVE_AXES)                     # 27 level combinations
FLIP_LOW_SHARE = 1 / 3   # of the combinations: a call that flips this often is low confidence
FLIP_LOW = round(FLIP_LOW_SHARE * COMBOS)        # 9 of 27
FLIP_WHY = (f"A lounge whose action changes in {FLIP_LOW} or more (a third) of the {COMBOS} combinations of "
            "drive time, competitor coverage and worker-housing share depends on the assumptions more than on "
            f"the data, so its call is low confidence. {LIVE_AXES_WHY}")
NEUTRAL = 0.5  # a missing or fallback rent scores here, never as the worst
THIN_MARKET = 10
THIN_MARKET_WHY = ("Under 10 premium salons in the catchment (al-dhafra, al-falah), capture is a share of a tiny "
                   "pool, so it is noisy: the lounge page flags it (thin_premium_market). Capture is shown, not "
                   "scored, so a thin market changes no call; served demand already splits each cell by reviews.")
WEIGHT_STEPS = (0.75, 1.25)
WEIGHT_WHY = ("The weights are a design choice, not data. Each signal's weight is moved ×0.75 and ×1.25, "
              "one at a time (8 variants); a call that changes under any of them depends on the weighting, "
              "so it is low confidence. The decision lines aren't varied: within 0.05 of one is already low.")
NO_FINANCIALS = ("No revenue, lease or footfall data: the only money scored is the site's shop rent per m² against "
                 "its emirate's median salon site, so this scores location, market and rent, not return on invested "
                 "capital.")


def score(signal: Signal, value: float | None) -> float:
    if value is None:
        return NEUTRAL
    return max(0.0, min(1.0, (value - signal.worst) / (signal.best - signal.worst)))


LOW_MARGIN = 0.05   # composite this close to a line: low confidence
HIGH_MARGIN = 0.10  # this far from both lines: high confidence


def _confidence(composite: float, low: bool, rules: Rules = RULES) -> str:
    margin = min(abs(composite - rules.protect_at), abs(composite - rules.shrink_at))
    if low or margin < LOW_MARGIN:
        return "low"
    return "high" if margin >= HIGH_MARGIN else "medium"


def _action(composite: float, rules: Rules = RULES) -> str:
    return "PROTECT" if composite >= rules.protect_at else "SHRINK" if composite <= rules.shrink_at else "HOLD"


def weights(rules: Rules = RULES) -> dict[str, float]:
    """Signal weights under these rules: demand_weight 0.5 gives each signal its own weight (1, 1)."""
    share = {"demand": rules.demand_weight, "cost": 1 - rules.demand_weight}
    return {s.name: s.weight * 2 * share[s.name] for s in SIGNALS}


def _composite(scores: dict[str, float], weights: dict[str, float]) -> float:
    return sum(weights[n] * scores[n] for n in weights) / sum(weights.values())


def weight_flips(scores: dict[str, float], rules: Rules = RULES) -> list[str]:
    """The weight variants (each signal ×0.75 or ×1.25, one at a time) that change the call."""
    base = weights(rules)
    action = _action(_composite(scores, base), rules)
    out = []
    for s in SIGNALS:
        if not base[s.name]:
            continue
        for step in WEIGHT_STEPS:
            new = _action(_composite(scores, {**base, s.name: base[s.name] * step}), rules)
            if new != action:
                out.append(f"{s.name} weight ×{step:g} → {new}")
    return out


def _decide(f: LoungeFeatures, flips: int | None, rules: Rules = RULES) -> Decision:
    if f.not_scored:
        return Decision(branch_id=f.branch_id, action="NOT SCORED", confidence="low",
                        rationale="Not scored: this lounge serves travellers, not the women in its catchment.",
                        key_drivers=[], caveats=[])
    fallback = rent_fallback(f)    # growth.RENT_FALLBACK_WHY: the emirate median is no observation of the site
    scores = {s.name: score(s, None if fallback and s.name == "cost" else getattr(f, s.field)) for s in SIGNALS}
    composite = _composite(scores, weights(rules))
    action = _action(composite, rules)
    caveats = [NO_FINANCIALS]
    if fallback:
        caveats.append(f"Site shop rent is the {f.emirate} median, not observed (no DLD, ADREC or listings rent in "
                       "its cell): rent scores neutral.")
    flippy = flips is not None and flips >= FLIP_LOW
    if flippy:
        caveats.append(f"The call changes in {flips} of {COMBOS} assumption combinations.")
    wflips = weight_flips(scores, rules)
    if wflips:
        caveats.append("The call depends on the signal weights: it changes with " + "; ".join(wflips) + ".")
    return Decision(
        branch_id=f.branch_id, action=action, weight_flips=wflips,
        confidence=_confidence(composite, flippy or bool(wflips) or fallback, rules),
        rationale=(f"Composite {composite:.2f} across site demand and site rent "
                   f"(PROTECT ≥ {rules.protect_at:g}, SHRINK ≤ {rules.shrink_at:g})."),
        key_drivers=sorted(scores, key=lambda n: abs(scores[n] - NEUTRAL), reverse=True)[:2],
        caveats=caveats, composite=round(composite, 4), scores={k: round(v, 4) for k, v in scores.items()})


def decide(features: list[LoungeFeatures], flips: dict[str, int] | None = None,
           rules: Rules = RULES) -> list[Decision]:
    """`flips`: per lounge, how many of the COMBOS live-axis level combinations change its action (level_flips)."""
    return [_decide(f, (flips or {}).get(f.branch_id), rules) for f in features]


def level_flips(v3, assumptions, levels, closed=frozenset(), rules: Rules = RULES,
                quotes: dict[str, float] | None = None) -> dict[str, int]:
    """How many of the COMBOS combinations of LIVE_AXES levels (other axes as in `levels`) give each
    lounge a different action than `levels`, under these rules and rent quotes."""
    from src.features.lounges import (  # here, not at the top: build doesn't need the scorecard
        build,
        with_quotes,
    )

    def actions(lv):
        feats = with_quotes(build(v3, assumptions, lv, closed, areas=False)[0], quotes)
        return {d.branch_id: d.action for d in decide(feats, rules=rules)}

    base = actions(levels)
    out = Counter()
    for lv in product(("low", "medium", "high"), repeat=len(LIVE_AXES)):
        for b, a in actions(replace(levels, **dict(zip(LIVE_AXES, lv, strict=True)))).items():
            out[b] += a != base[b]
    return {b: out[b] for b in base}


def counts(decisions: list[Decision]) -> dict[str, int]:
    """PROTECT / HOLD / SHRINK counts; NOT SCORED lounges are left out."""
    c = Counter(d.action for d in decisions)
    return {a: c[a] for a in ("PROTECT", "HOLD", "SHRINK")}
