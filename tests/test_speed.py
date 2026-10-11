"""Regression guard: a baseline run() must stay fast. Measured 2026-10-11 on an M-series Mac:
~4.1 s with the on-disk access table, ~4.3 s without it (was ~44 s before the numpy allocate).
Thresholds keep ~2x headroom."""
import time

from src import baseline
from src.features import lounges as L
from src.model import served as S

WARM_S = 8.0    # in-memory caches cleared, disk access table kept
COLD_S = 10.0   # and no disk access table


def _timed_run() -> float:
    baseline._run.cache_clear()
    for c in (L._SERVED, L._PREP, S._ACCESS, S._IMPUTED, S._COMPETITORS, S._BASE):
        c.clear()
    t = time.perf_counter()
    baseline.run()
    return time.perf_counter() - t


def test_cold_run_is_fast(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "ACCESS_CACHE", tmp_path)
    assert (t := _timed_run()) < COLD_S, f"cold run() took {t:.1f}s"


def test_warm_run_is_fast():
    _timed_run()   # makes sure the disk access table exists
    assert (t := _timed_run()) < WARM_S, f"warm run() took {t:.1f}s"
