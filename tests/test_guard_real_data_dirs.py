"""Proves the autouse `_guard_real_data_dirs` fixture in conftest.py actually fires."""

import shutil

import pytest

from src.config import REPO_ROOT


def test_guard_refuses_to_rmtree_real_raw_dir_subpath():
    scratch = REPO_ROOT / "data" / "raw" / "test-guard-scratch"
    scratch.mkdir(parents=True, exist_ok=False)
    try:
        with pytest.raises(RuntimeError, match="real repo data directory"):
            shutil.rmtree(scratch)
        assert scratch.exists()
    finally:
        scratch.rmdir()


def test_guard_leaves_tmp_path_rmtree_unaffected(tmp_path):
    victim = tmp_path / "some_dir"
    victim.mkdir()
    (victim / "f.txt").write_text("x")
    shutil.rmtree(victim)  # must not raise
    assert not victim.exists()


def test_guard_allows_rmtree_on_a_protected_path_that_does_not_exist():
    nonexistent = REPO_ROOT / "data" / "raw" / "test-guard-scratch-nonexistent"
    assert not nonexistent.exists()
    shutil.rmtree(nonexistent, ignore_errors=True)  # must not raise
