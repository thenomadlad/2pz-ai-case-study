"""Proves the autouse `_guard_real_data_dirs` fixture in conftest.py actually fires.

See the incident recorded in src/scenario/baseline.py's history: a test that
forgot to pin `processed_dir` to a tmp_path let a legitimate `shutil.rmtree`
call delete the real repo's data/processed/current/ directory. This test
creates a real (non-tmp_path) scratch directory under the protected tree,
attempts to rmtree it, and asserts that the guard refuses -- proving the
directory survives rather than merely that the call didn't crash.
"""

import shutil

from src.config import REPO_ROOT


def test_guard_refuses_to_rmtree_real_processed_dir():
    scratch = REPO_ROOT / "data" / "processed" / "test-guard-scratch"
    scratch.mkdir(parents=True, exist_ok=False)
    try:
        (scratch / "marker.txt").write_text("should survive the refused rmtree")

        import pytest

        with pytest.raises(RuntimeError, match="real repo data directory"):
            shutil.rmtree(scratch)

        # Prove the guard actually fired (not just that rmtree happened to no-op):
        # the directory and its contents must still be exactly as created.
        assert scratch.exists()
        assert (scratch / "marker.txt").exists()
        assert (scratch / "marker.txt").read_text() == "should survive the refused rmtree"
    finally:
        # Clean up directly (bypassing the guarded shutil.rmtree) so this test's
        # teardown doesn't depend on the very thing it's testing.
        (scratch / "marker.txt").unlink(missing_ok=True)
        scratch.rmdir()


def test_guard_refuses_to_rmtree_real_raw_dir_subpath():
    scratch = REPO_ROOT / "data" / "raw" / "test-guard-scratch"
    scratch.mkdir(parents=True, exist_ok=False)
    try:
        import pytest

        with pytest.raises(RuntimeError, match="real repo data directory"):
            shutil.rmtree(scratch)

        assert scratch.exists()
    finally:
        scratch.rmdir()


def test_guard_leaves_tmp_path_rmtree_unaffected(tmp_path):
    victim = tmp_path / "some_dir"
    victim.mkdir()
    (victim / "f.txt").write_text("x")

    # Must NOT raise -- tmp_path is exactly what the test suite should use.
    shutil.rmtree(victim)

    assert not victim.exists()
