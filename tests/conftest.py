import shutil
from pathlib import Path

import pytest

from src.config import REPO_ROOT

_PROTECTED_DIRS = (
    (REPO_ROOT / "data" / "raw").resolve(),
    (REPO_ROOT / "data" / "processed").resolve(),
)


@pytest.fixture(autouse=True)
def _guard_real_data_dirs(monkeypatch):
    """Refuse to rmtree the real repo's data/raw or data/processed during tests.

    A prior incident: a test that forgot to override `processed_dir` let a
    legitimate `shutil.rmtree` call in production code (src/scenario/baseline.py's
    `main()`) delete the real repo's data/processed/current/ directory. This guard
    makes that class of mistake fail loudly instead of silently succeeding, while
    leaving rmtree calls on tmp_path-based directories (what tests should use)
    completely unaffected.
    """
    real_rmtree = shutil.rmtree

    def guarded_rmtree(path, *args, **kwargs):
        resolved = Path(path).resolve()
        for protected in _PROTECTED_DIRS:
            if resolved == protected or protected in resolved.parents:
                raise RuntimeError(
                    f"Test attempted to rmtree a real repo data directory: {resolved}. "
                    "This usually means a Settings object was constructed without "
                    "overriding raw_dir/processed_dir to a tmp_path. Refusing."
                )
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(shutil, "rmtree", guarded_rmtree)
