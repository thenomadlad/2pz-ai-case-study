import math

import pytest

from src.baseline import diff, run
from src.config import REPO_ROOT, load_baseline_assumptions
from src.models import Levels


def by_id(rows):
    return {r.branch_id: r for r in rows}


def test_baseline_has_24_decisions_one_not_scored():
    r = run()
    assert len(r.decisions) == 24
    assert sum(d.action == "NOT SCORED" for d in r.decisions) == 1


def test_closing_al_barsha_moves_neighbours_and_opens_no_core_area():
    base, after = run(), run(closed=frozenset({"al-barsha"}))
    b, a = by_id(base.features), by_id(after.features)
    assert "al-barsha" not in a
    for n in ("jumeirah-park", "city-walk"):
        assert a[n].shared_share != b[n].shared_share
    # capture moves only where the closed lounge was among the substitutes (city-walk, not jumeirah-park)
    assert a["city-walk"].capture != b["city-walk"].capture
    d = diff(base, after)
    # small fringe areas do open up (al-sufouh, mudon...), but none is worth growing into
    acts = {x.area_id: x.action for x in after.area_decisions}
    assert d.areas_appeared and all(acts[i] == "SKIP" for i in d.areas_appeared)
    assert all(x.women < 10_000 for x in after.areas if x.area_id in d.areas_appeared)
    assert {c.branch_id for c in d.lounges} >= {"al-barsha", "jumeirah-park", "city-walk"}
    assert next(c for c in d.lounges if c.branch_id == "al-barsha").new_action is None


def test_high_travel_raises_every_catchment():
    base, hi = by_id(run().features), by_id(run(Levels(travel="high")).features)
    assert all(hi[k].catchment_women >= base[k].catchment_women for k in base)
    assert any(hi[k].catchment_women > base[k].catchment_women for k in base)


def test_unknown_closed_id_raises_naming_it():
    with pytest.raises(ValueError, match="nope"):
        run(closed=frozenset({"nope"}))


def test_closing_every_scored_lounge_raises():
    ids = frozenset(d.branch_id for d in run().decisions if d.action != "NOT SCORED")
    with pytest.raises(ValueError):
        run(closed=ids)


def test_search_recall_override_changes_capture():
    assert run(search_recall=0.3).features != run().features


def test_no_nan_when_one_lounge_left():
    ids = frozenset(d.branch_id for d in run().decisions if d.action != "NOT SCORED")
    keep = sorted(ids)[0]
    r = run(closed=ids - {keep})
    assert all(not math.isnan(a.nearest_lounge_km) and a.nearest_lounge_id for a in r.areas)


def test_diff_of_same_run_is_empty():
    assert diff(run(), run(search_recall=load_baseline_assumptions(
        REPO_ROOT / "data" / "scenarios" / "baseline.yaml").search_recall)).empty


def test_mutating_a_returned_run_does_not_leak():
    r, action = run(), run().decisions[0].action
    r.features.clear()
    r.decisions[0].action = "SHRINK" if action != "SHRINK" else "HOLD"
    again = run()
    assert len(again.features) == 24 and again.decisions[0].action == action
