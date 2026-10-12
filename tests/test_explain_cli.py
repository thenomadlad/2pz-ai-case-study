import subprocess
import sys


def test_unknown_or_help_arguments_never_reach_the_paid_api():
    """Regression: `python -m src.explain --help` used to fall through to main(), the paid-API path."""
    for args in (["--help"], [], ["promts", "x"], ["api", "extra"]):
        out = subprocess.run([sys.executable, "-m", "src.explain", *args], capture_output=True, text=True,
                             env={"PATH": "", "ANTHROPIC_API_KEY": "sk-test-not-a-key"}, timeout=60)
        assert out.returncode != 0 and "usage: python -m src.explain" in out.stderr, args
