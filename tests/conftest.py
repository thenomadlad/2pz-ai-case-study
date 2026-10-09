import shutil
from pathlib import Path

import pytest

from src.config import REPO_ROOT

_PROTECTED_DIRS = ((REPO_ROOT / "data" / "raw").resolve(),)


@pytest.fixture(autouse=True)
def _guard_real_data_dirs(monkeypatch):
    """Refuse to rmtree the real repo's data/raw during tests.

    data/raw holds the fetch scripts' API response caches (Google Places, Mapbox) and the
    WorldPop / OSM downloads: expensive or slow to rebuild. A test that rmtrees a real, existing
    directory under it fails loudly; tmp_path directories and paths that don't exist are
    unaffected.
    """
    real_rmtree = shutil.rmtree

    def guarded_rmtree(path, *args, **kwargs):
        resolved = Path(path).resolve()
        if not resolved.exists():
            return real_rmtree(path, *args, **kwargs)
        for protected in _PROTECTED_DIRS:
            if resolved == protected or protected in resolved.parents:
                raise RuntimeError(
                    f"Test attempted to rmtree a real repo data directory: {resolved}. "
                    "Use a tmp_path instead. Refusing."
                )
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(shutil, "rmtree", guarded_rmtree)
