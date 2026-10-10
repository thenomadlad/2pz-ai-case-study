"""What the app shows: the baseline run, or the what-if the user set on the Overview.

The what-if lives in st.session_state["what_if"] (not in widget keys, which Streamlit drops on
pages that don't render the widget), so every page sees it."""
from functools import cache, lru_cache

import pandas as pd
import streamlit as st

from src import explain
from src.baseline import Run, run
from src.config import REPO_ROOT, load_baseline_assumptions
from src.data_v3 import V3, load_v3
from src.market import women_15plus
from src.models import BaselineAssumptions, Levels

BASELINE_YAML = REPO_ROOT / "data" / "scenarios" / "baseline.yaml"


@cache
def assumptions() -> BaselineAssumptions:
    return load_baseline_assumptions(BASELINE_YAML)


def v3() -> V3:
    return load_v3()


def what_if() -> dict:
    """{"levels": Levels, "closed": frozenset, "recall": float | None (None = baseline)}."""
    return st.session_state.setdefault(
        "what_if", {"levels": Levels(), "closed": frozenset(), "recall": None})


def active() -> bool:
    w = what_if()
    return w["levels"] != Levels() or bool(w["closed"]) or w["recall"] is not None


@lru_cache(maxsize=64)
def _run(levels: Levels, closed: frozenset[str], recall: float | None) -> Run:
    return run(levels, closed, recall)     # run() deep-copies; keep one copy per what-if


def current() -> Run:
    """The run for the current what-if: the same object for the same what-if, so treat it as read-only."""
    w = what_if()
    return _run(w["levels"], w["closed"], w["recall"])


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
    """Cell -> the open lounges whose catchment reaches it."""
    c = v3().catchment
    c = c[(c.level == levels.travel) & ~c.branch_id.isin(closed)]
    return c.groupby("cell_id").branch_id.agg(list).to_dict()


def address(branch_id: str) -> str:
    return next(lo.address for lo in v3().lounges if lo.branch_id == branch_id)
