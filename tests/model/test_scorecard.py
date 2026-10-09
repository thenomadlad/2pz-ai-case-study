import pytest

from src.config import REPO_ROOT
from src.model.scorecard import FLIP_LOW, PROTECT_AT, SHRINK_AT, SIGNALS, counts, decide, score
from src.models import LoungeFeatures

SIG = {s.name: s for s in SIGNALS}


def _f(b="a", women=100_000.0, shared=0.5, capture=0.075, gap=0.0, thin=False, not_scored=False):
    return LoungeFeatures(
        branch_id=b, name=b, emirate="Dubai", lat=25.0, lng=55.0, rating=4.5, review_count=100,
        catchment_women=women, catchment_cells=10, shared_share=shared, capture=capture,
        substitutes_k=5, recall_multiplier=1.0, premium_pool=5 if thin else 50,
        thin_premium_market=thin, substitutes_median_rating=4.5, rating_gap=gap,
        est_customers=capture * women, not_scored=not_scored)


@pytest.mark.parametrize("name", ["demand", "cannibalisation", "capture", "rating"])
def test_scores_on_the_anchors_and_clipped(name):
    s = SIG[name]
    assert score(s, s.worst) == 0 and score(s, s.best) == 1
    assert score(s, (s.worst + s.best) / 2) == pytest.approx(0.5)
    beyond = s.best + (s.best - s.worst)
    below = s.worst - (s.best - s.worst)
    assert score(s, beyond) == 1 and score(s, below) == 0


def test_drafted_anchors():
    assert [(s.field, s.worst, s.best) for s in SIGNALS] == [
        ("catchment_women", 0, 200_000), ("shared_share", 1.0, 0.0),
        ("capture", 0, 0.15), ("rating_gap", -0.3, 0.3)]
    assert all(s.why for s in SIGNALS)


def test_composite_is_the_weighted_mean_and_thresholds_split_actions():
    strong = _f("strong", women=200_000, shared=0, capture=0.15, gap=0.3)
    weak = _f("weak", women=0, shared=1, capture=0, gap=-0.3)
    mid = _f("mid")
    d = {x.branch_id: x for x in decide([strong, weak, mid])}
    assert d["strong"].composite == pytest.approx(1) and d["weak"].composite == pytest.approx(0)
    assert d["mid"].composite == pytest.approx(0.5)
    assert [d[i].action for i in ("strong", "mid", "weak")] == ["PROTECT", "HOLD", "SHRINK"]
    assert SHRINK_AT < PROTECT_AT


def test_thin_market_scores_capture_neutral_and_confidence_low():
    d = decide([_f(women=200_000, shared=0, capture=0.9, gap=0.3, thin=True)])[0]
    assert d.scores["capture"] == 0.5 and d.confidence == "low"
    assert any("thin" in c.lower() for c in d.caveats)


def test_missing_rating_gap_scores_neutral():
    assert decide([_f(gap=None)])[0].scores["rating"] == 0.5


def test_confidence_margin_rule():
    far = decide([_f(women=200_000, shared=0, capture=0.15, gap=0.3)])[0]
    # (0.27 + 1 + 1 + 0.5 x 0) / 3.5 = 0.648, within 0.05 of PROTECT_AT
    near = decide([_f(women=54_000, shared=0, capture=0.15, gap=-0.3)])[0]
    assert far.confidence == "high" and near.confidence == "low"


def test_not_scored_lounge_gets_no_call_and_is_not_counted():
    ds = decide([_f("airport", women=200_000, shared=0, capture=0.15, gap=0.3, not_scored=True), _f("mid")])
    air = ds[0]
    assert air.action == "NOT SCORED" and air.scores == {} and air.composite == 0
    assert counts(ds) == {"PROTECT": 0, "HOLD": 1, "SHRINK": 0}


def test_score_does_not_depend_on_siblings():
    a = _f("a", women=80_000, shared=0.3, capture=0.05, gap=-0.1)
    assert decide([a])[0] == decide([a, _f("b", women=500_000)])[0]


def test_rating_has_half_weight():
    d = decide([_f(women=0, shared=1, capture=0, gap=0.3)])[0]
    assert d.composite == pytest.approx(0.5 / 3.5, abs=1e-4)


def test_lounges_that_flip_often_are_low_confidence():
    strong = _f(women=200_000, shared=0, capture=0.15, gap=0.3)
    assert decide([strong], flips={"a": FLIP_LOW - 1})[0].confidence == "high"
    d = decide([strong], flips={"a": FLIP_LOW})[0]
    assert d.confidence == "low" and any("27" in c for c in d.caveats)


def test_level_flips_on_real_data():
    from src.config import load_baseline_assumptions
    from src.data_v3 import load_v3
    from src.models import Levels
    from src.model.scorecard import level_flips
    a = load_baseline_assumptions(REPO_ROOT / "data" / "scenarios" / "baseline.yaml")
    flips = level_flips(load_v3(), a, Levels())
    assert len(flips) == 24 and all(0 <= n <= 26 for n in flips.values())
    assert flips["zayed-international-airport"] == 0
