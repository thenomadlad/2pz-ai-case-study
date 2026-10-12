"""What the app shows: the baseline run everywhere, and the what-if the user set on the What-if explorer
(only that page reads it).

The what-if lives in st.session_state["what_if"] (not in widget keys, which Streamlit drops on
pages that don't render the widget), so every page sees it."""
import dataclasses
from functools import cache, lru_cache

import pandas as pd
import streamlit as st

from src import explain
from src.baseline import Run, run
from src.config import REPO_ROOT, load_baseline_assumptions
from src.data_v3 import V3, load_v3
from src.features.lounges import NOT_SCORED
from src.market import women_15plus
from src.models import BaselineAssumptions, Levels, Rules

BASELINE_YAML = REPO_ROOT / "data" / "scenarios" / "baseline.yaml"


@cache
def assumptions() -> BaselineAssumptions:
    return load_baseline_assumptions(BASELINE_YAML)


def v3() -> V3:
    return load_v3()


def empty_what_if() -> dict:
    return {"levels": Levels(), "closed": frozenset(), "recall": None, "rules": Rules(), "quotes": {}}


def what_if() -> dict:
    """{"levels": Levels, "closed": frozenset, "recall": float | None (None = baseline), "rules": Rules,
    "quotes": {site id: AED/m²/yr}}."""
    w = st.session_state.setdefault("what_if", empty_what_if())
    for k, v in empty_what_if().items():
        w.setdefault(k, v)
    for k, cls in (("levels", Levels), ("rules", Rules)):
        if type(w[k]) is not cls:   # a dev hot-reload re-imported src.models: rebuild from the old instance
            w[k] = cls(**dataclasses.asdict(w[k]))
    return w


def active() -> bool:
    w = what_if()
    return (w["levels"] != Levels() or bool(w["closed"]) or w["recall"] is not None
            or w["rules"] != Rules() or bool(w["quotes"]))


@lru_cache(maxsize=64)
def _run(levels: Levels, closed: frozenset[str], recall: float | None, rules: Rules = Rules(),  # noqa: B008
         quotes: tuple = ()) -> Run:
    return run(levels, closed, recall, rules, dict(quotes))     # run() deep-copies; keep one copy per what-if


def baseline() -> Run:
    """The baseline run: what every page except the What-if explorer shows. Treat it as read-only."""
    return _run(Levels(), frozenset(), None)


def current() -> Run:
    """The What-if explorer's run for the current what-if: the same object for the same what-if, so treat it as read-only."""
    w = what_if()
    return _run(w["levels"], w["closed"], w["recall"], w["rules"], tuple(sorted(w["quotes"].items())))


_SUBJECTS: dict[int, tuple[Run, dict]] = {}


def subject(r: Run, kind: str, subject_id: str) -> tuple[str, dict]:
    """(action, facts) for one explanation of this run, built exactly as the cache was."""
    hit = _SUBJECTS.get(id(r))
    if not hit or hit[0] is not r:
        if len(_SUBJECTS) > 64:     # as many as baseline.run keeps
            _SUBJECTS.clear()
        hit = _SUBJECTS[id(r)] = (r, {(k, sid): (a, f) for k, sid, a, f in explain.run_subjects(r)})
    return hit[1][(kind, subject_id)]


@cache
def women(worker_level: str) -> pd.Series:
    """Women 15+ per cell at a worker-housing level."""
    d = v3()
    return women_15plus(d.cells, d.emirates, assumptions().worker_housing_female_share[worker_level])


def rents() -> pd.Series:
    """Observed median household rent per cell (AED/yr), only where DLD data exists (Dubai)."""
    return v3().cells.rent_observed.dropna()


def minutes(levels: Levels) -> int:
    return assumptions().travel_time_minutes[levels.travel]


def catchment(levels: Levels, branch_id: str) -> list[str]:
    c = v3().catchment
    return c[(c.level == levels.travel) & (c.branch_id == branch_id)].cell_id.tolist()


def reached(levels: Levels, closed: frozenset[str]) -> dict[str, list[str]]:
    """Cell -> the open, scored lounges whose catchment reaches it (as shared_share counts them)."""
    c = v3().catchment
    c = c[(c.level == levels.travel) & ~c.branch_id.isin(closed) & ~c.branch_id.isin(NOT_SCORED)]
    return c.groupby("cell_id").branch_id.agg(list).to_dict()


def address(branch_id: str) -> str:
    return next(lo.address for lo in v3().lounges if lo.branch_id == branch_id)


AXES = (("travel", "Drive time"), ("coverage", "Competitor coverage"),
        ("worker_share", "Women in worker housing"))   # scorecard.LIVE_AXES
LEVELS = ("low", "medium", "high")


@lru_cache(maxsize=16)
def at_level(axis: str, level: str) -> tuple[dict, dict, float]:
    """The baseline with one assumption moved: {lounge: (features, decision)}, {area: (area, decision)} and the
    women our lounges serve. No confidence check (level_flips), so it builds in well under 2 s."""
    from src.features.lounges import build
    from src.model import growth, scorecard
    levels = Levels(**{**dataclasses.asdict(Levels()), axis: level})
    feats, areas = build(v3(), assumptions(), levels)
    return ({f.branch_id: (f, d) for f, d in zip(feats, scorecard.decide(feats))},
            {a.area_id: (a, d) for a, d in zip(areas, growth.classify_all(areas))},
            sum(f.served_women or 0 for f in feats))
