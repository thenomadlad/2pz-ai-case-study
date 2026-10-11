import pytest

from src.config import REPO_ROOT
from src.model.scorecard import (
    COMBOS,
    FLIP_LOW,
    FLIP_LOW_SHARE,
    PROTECT_AT,
    SHRINK_AT,
    SIGNALS,
    counts,
    decide,
    score,
)
from src.models import LoungeFeatures

SIG = {s.name: s for s in SIGNALS}


# Served-demand model 2026-10-11: two signals, demand (site served: a typical lounge at the site) and
# cost (cost index vs the frozen UAE-wide anchor). The
# capture / rating / cannibalisation signals and their tests (thin-market blend, rating half weight,
# missing rating gap) are gone with them; cannibalisation is display only.
def _f(b="a", served=10_000.0, cost=1.0, not_scored=False):
    return LoungeFeatures(
        branch_id=b, name=b, emirate="Dubai", lat=25.0, lng=55.0, rating=4.5, review_count=100,
        catchment_women=50_000, addressable_women=50_000, affluence_rent=None, affluence_coverage=0.0,
        catchment_cells=10, shared_share=0.5, capture=0.1, substitutes_k=5, recall_multiplier=1.0,
        premium_pool=50, thin_premium_market=False, substitutes_median_rating=4.5, rating_gap=0.0,
        est_customers=5_000, served_women=served, site_served=served, cost_index=cost, not_scored=not_scored)


@pytest.mark.parametrize("name", ["demand", "cost"])
def test_scores_on_the_anchors_and_clipped(name):
    s = SIG[name]
    assert score(s, s.worst) == 0 and score(s, s.best) == 1
    assert score(s, (s.worst + s.best) / 2) == pytest.approx(0.5)
    beyond = s.best + (s.best - s.worst)
    below = s.worst - (s.best - s.worst)
    assert score(s, beyond) == 1 and score(s, below) == 0


def test_drafted_anchors():
    assert [(s.field, s.worst, s.best, s.weight) for s in SIGNALS] == [
        ("site_served", 0, 20_000, 1.0), ("cost_index", 0.5, 1.5, 1.0)]
    assert all(s.why for s in SIGNALS)


def test_composite_is_the_weighted_mean_and_thresholds_split_actions():
    strong, weak, mid = _f("strong", 20_000, 1.5), _f("weak", 0, 0.5), _f("mid")
    d = {x.branch_id: x for x in decide([strong, weak, mid])}
    assert d["strong"].composite == pytest.approx(1) and d["weak"].composite == pytest.approx(0)
    assert d["mid"].composite == pytest.approx(0.5)
    assert [d[i].action for i in ("strong", "mid", "weak")] == ["PROTECT", "HOLD", "SHRINK"]
    assert SHRINK_AT < PROTECT_AT


def test_missing_cost_index_scores_neutral():
    assert decide([_f(cost=None)])[0].scores["cost"] == 0.5


def test_confidence_margin_rule():
    far = decide([_f(served=20_000, cost=1.5)])[0]
    near = decide([_f(served=16_000, cost=1.0)])[0]       # (0.8 + 0.5) / 2 = 0.65: on the PROTECT line
    assert far.confidence == "high" and near.confidence == "low"


def test_not_scored_lounge_gets_no_call_and_is_not_counted():
    ds = decide([_f("airport", 20_000, 1.5, not_scored=True), _f("mid")])
    air = ds[0]
    assert air.action == "NOT SCORED" and air.scores == {} and air.composite == 0
    assert counts(ds) == {"PROTECT": 0, "HOLD": 1, "SHRINK": 0}


def test_score_does_not_depend_on_siblings():
    a = _f("a", served=8_000, cost=0.8)
    assert decide([a])[0] == decide([a, _f("b", served=50_000)])[0]


def test_lounges_that_flip_often_are_low_confidence():
    strong = _f(served=20_000, cost=1.5)
    assert decide([strong], flips={"a": FLIP_LOW - 1})[0].confidence == "high"
    d = decide([strong], flips={"a": FLIP_LOW})[0]
    assert d.confidence == "low" and any("of 81" in c for c in d.caveats)


def test_level_flips_on_real_data():
    from src.config import load_baseline_assumptions
    from src.data_v3 import load_v3
    from src.model.scorecard import level_flips
    from src.models import Levels
    a = load_baseline_assumptions(REPO_ROOT / "data" / "scenarios" / "baseline.yaml")
    flips = level_flips(load_v3(), a, Levels())
    assert len(flips) == 24 and all(0 <= n <= 80 for n in flips.values())
    assert flips["zayed-international-airport"] == 0


def test_a_call_that_flips_with_a_signal_weight_is_low_confidence():
    # Run-2 fix B3: each weight ×0.75 / ×1.25, one at a time (served-demand model 2026-10-11).
    # Demand 1, cost 0.25: 0.625 HOLD; demand ×1.25 gives 1.5 / 2.25 = 0.667 PROTECT,
    # cost ×0.75 gives 1.1875 / 1.75 = 0.679 PROTECT.
    d = decide([_f(served=20_000, cost=0.75)])[0]
    assert d.action == "HOLD" and d.weight_flips == ["demand weight ×1.25 → PROTECT", "cost weight ×0.75 → PROTECT"]
    assert d.confidence == "low" and any("signal weights" in c for c in d.caveats)
    far = decide([_f()])[0]
    assert far.weight_flips == [] and far.confidence == "high"


def test_flip_line_is_a_third_of_the_81_combinations():
    assert COMBOS == 81 and FLIP_LOW_SHARE == 1 / 3 and FLIP_LOW == 27


def test_level_flips_iterates_81_combinations_fast():
    import time

    from src.config import load_baseline_assumptions
    from src.data_v3 import load_v3
    from src.features import lounges
    from src.model.scorecard import level_flips
    from src.models import Levels
    a = load_baseline_assumptions(REPO_ROOT / "data" / "scenarios" / "baseline.yaml")
    v3, seen, real = load_v3(), [], lounges.build
    lounges.build = lambda *args, **kw: seen.append(args[2]) or real(*args, **kw)
    try:
        start = time.perf_counter()
        level_flips(v3, a, Levels())
        took = time.perf_counter() - start
    finally:
        lounges.build = real
    assert len(set(seen)) == 81 and took < 4     # ~1 s here; slack for slower machines
