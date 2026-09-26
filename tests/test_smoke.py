# tests/test_smoke.py
import sys


def test_python_version():
    assert sys.version_info >= (3, 11)


def test_src_importable():
    import src  # noqa: F401
