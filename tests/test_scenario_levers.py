"""The portfolio team's levers on the What-if explorer: decision rules (Rules) and rent quotes."""
import dataclasses

import pytest

from src.baseline import diff, run
from src.model import growth, scorecard
from src.models import Rules


def _calls(decisions):
    return {d.branch_id: d.action for d in decisions}


def test_default_rules_are_the_baseline_lines():
    assert dataclasses.asdict(Rules()) == {"demand_weight": 0.5, "protect_at": 0.65, "shrink_at": 0.35,
                                           "grow_min": 6_000, "demand_pct_min": 0.5}
    assert (scorecard.PROTECT_AT, scorecard.SHRINK_AT) == (0.65, 0.35)
    assert (growth.NEW_SITE_MIN, growth.DEMAND_PCT_MIN) == (6_000, 0.5)
    assert scorecard.weights(Rules()) == {s.name: s.weight for s in scorecard.SIGNALS} == {"demand": 1.0, "cost": 1.0}


def test_default_rules_reproduce_the_baseline_exactly():
    """Every call, composite, score and confidence: explicit default rules = no rules = equal weights, lines 0.65/0.35."""
    r = run()
    again = scorecard.decide(r.features, r.flips, Rules(**dataclasses.asdict(Rules())))
    assert [d.model_dump() for d in again] == [d.model_dump() for d in r.decisions]
    assert ([d.model_dump() for d in growth.classify_all(r.areas, Rules())]
            == [d.model_dump() for d in r.area_decisions])
    for d in r.decisions:
        if d.action != "NOT SCORED":
            c = (d.scores["demand"] + d.scores["cost"]) / 2
            assert abs(d.composite - c) <= 1e-4          # scores are stored rounded to 4 places
            assert d.action == ("PROTECT" if c >= 0.65 else "SHRINK" if c <= 0.35 else "HOLD")


def test_rent_quote_rescores_only_that_site():
    base, q = run(), run(quotes={"city-walk": 2_200})
    b, a = {d.branch_id: d for d in base.decisions}, {d.branch_id: d for d in q.decisions}
    assert (b["city-walk"].action, a["city-walk"].action) == ("SHRINK", "HOLD")
    assert a["city-walk"].scores["demand"] == b["city-walk"].scores["demand"]      # rent doesn't feed demand
    assert a["city-walk"].scores["cost"] > b["city-walk"].scores["cost"]
    f = next(f for f in q.features if f.branch_id == "city-walk")
    assert (f.site_rent_m2, f.site_rent_source) == (2_200, "quote")
    assert [c.branch_id for c in diff(base, q).lounges] == ["city-walk"]
    assert _calls(run(quotes={"city-walk": 3_200}).decisions)["city-walk"] == "SHRINK"


def test_a_quote_clears_the_fallback_rent_flag():
    base = {d.branch_id: d for d in run().decisions}["al-ain"]
    quoted = {d.branch_id: d for d in run(quotes={"al-ain": 1_100}).decisions}["al-ain"]
    assert any("not observed" in c for c in base.caveats) and base.confidence == "low"
    assert not any("not observed" in c for c in quoted.caveats) and quoted.confidence != "low"


def test_area_quote_moves_the_grow_rent_test():
    r = run()
    grow = next(a for a, d in zip(r.areas, r.area_decisions) if d.action == "GROW" and a.rent_ratio)
    dear = grow.shop_rent_m2 * grow.rent_ratio * 2     # twice its emirate's median salon-site rent
    q = run(quotes={grow.area_id: dear})
    assert {d.area_id: d.action for d in q.area_decisions}[grow.area_id] == "WATCH"


def test_tightening_the_grow_minimum_never_adds_grow():
    r = run()
    counts = [sum(d.action == "GROW" for d in growth.classify_all(r.areas, Rules(grow_min=m)))
              for m in range(2_000, 20_001, 1_000)]
    assert counts == sorted(counts, reverse=True)
    assert counts[(10_000 - 2_000) // 1_000] < counts[(6_000 - 2_000) // 1_000]


def test_weights_and_lines_move_the_expected_calls():
    r = run()
    calls = _calls(r.decisions)
    demand_heavy = _calls(scorecard.decide(r.features, r.flips, Rules(demand_weight=0.7)))
    assert (calls["baniyas"], demand_heavy["baniyas"]) == ("HOLD", "PROTECT")      # demand 0.99, rent 0.10
    assert (calls["khaleej-al-arabi"], demand_heavy["khaleej-al-arabi"]) == ("HOLD", "SHRINK")   # demand 0.22
    rent_only = scorecard.decide(r.features, r.flips, Rules(demand_weight=0))
    assert all(d.composite == d.scores["cost"] for d in rent_only if d.action != "NOT SCORED")
    strict = _calls(scorecard.decide(r.features, r.flips, Rules(protect_at=0.7, shrink_at=0.4)))
    assert (calls["al-falah"], strict["al-falah"]) == ("PROTECT", "HOLD")          # composite 0.66
    assert (calls["delma"], strict["delma"]) == ("HOLD", "SHRINK")                 # composite 0.38


def test_shrink_line_must_stay_below_protect():
    with pytest.raises(ValueError, match="SHRINK line"):
        run(rules=Rules(protect_at=0.5, shrink_at=0.5))
