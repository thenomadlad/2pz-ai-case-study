"""Retired ideas must not come back as current. Each entry is a phrase from an earlier model or an
earlier app, and why it's gone. A sentence may still name one when it says so (dropped, retired,
replaced...); sections about what we dropped, glossary "_Avoid_" lines, the audit logs and the archived
notebooks are history, so they're skipped. Prose is checked sentence by sentence, code line by line."""
import json
import re
import subprocess

from src.config import REPO_ROOT

PROSE, ALL = (".md", ".ipynb"), (".md", ".ipynb", ".py")
RETIRED = {   # pattern: (why it's retired, which files it applies to)
    r"cost index|COST_ANCHOR": ("the UAE-wide cost index is gone; rent is the rent ratio within the emirate", ALL),
    r"capture score|scor\w* (on )?capture": ("capture is shown, never scored (Huff already splits each cell)", ALL),
    r"\b81\b[^.\n]{0,30}combination|27\+ of": ("the confidence check is 9+ of 27 combinations", ALL),
    r"four levelled": ("three assumptions are varied (drive time, coverage, worker share); affluence is off", ALL),
    r"200k anchor|0 → 20k": ("site demand is a percentile of the emirate's salon sites", ALL),
    r"MIN_BASELINE_LOUNGES": ("the emirate-median-of-lounges baseline is gone", ALL),
    r"median reviews and rating": ("the typical lounge is frozen at 757 reviews, 4.6★", ALL),
    r"services (delivered|rendered)": ("the one term is services sold", ALL),
    r"\bCOO\b": ("the audience is the network and capital owner", ALL),
    r"All catchments \(overlap\)": ("every catchment is always drawn; the toggle is gone", ALL),
    r"\bHow page\b": ("the page is the README, under Documentation", ALL),
    r"Review, Grow,? (and )?Protect": ("the Executive Summary runs Review, Protect, Grow", ALL),
    # the code computing the two context figures legitimately uses it; prose must not present it as scored
    r"150 m²|150 m2|REF_UNIT_M2": ("rent per m² is the only cost scored; the 150 m² unit is context only", PROSE),
}
HISTORY = re.compile(r"dropped|retired|superseded|no longer|earlier|old model|previous|replaced|archived|instead of|"
                     r"context only|display only|not scored|no call uses|demoted|_Avoid_|\bwas\b|\bwere\b", re.IGNORECASE)
HISTORY_SECTION = re.compile(r"ignore|dropped|retired|history|context only|not scored", re.IGNORECASE)
SKIP = {"docs/rubric.md", "docs/sanity-checks.md",                                   # audit logs: history
        "notebooks/features/decisions.ipynb", "notebooks/features/features.ipynb"}   # archived notebooks


def _prose_units(text: str):
    """(line, sentence) for prose: paragraphs and list items joined, then split into sentences; a table
    row is one unit; sections whose heading is about what we dropped are skipped."""
    unit, start, section = [], 0, ""
    text = re.sub(r"(?m)^> ?", "", text)   # a blockquote is prose too

    def flush():
        joined = " ".join(unit)
        for s in ([joined] if joined.startswith("|") else re.split(r"(?<=[.!?])\s+", joined)):
            if s and not HISTORY_SECTION.search(section):
                yield start, s
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        new = not s or s.startswith(("#", "|", "- ", "* ")) or re.match(r"\d+\. ", s)
        if new and unit:
            yield from flush()
            unit = []
        if s.startswith("#"):
            section = s
            continue
        if s:
            unit, start = (unit + [s]) if unit else [s], start if unit else n
    if unit:
        yield from flush()


def _units():
    files = subprocess.run(["git", "ls-files", *(f"*{e}" for e in ALL)], cwd=REPO_ROOT,
                           capture_output=True, text=True, check=True).stdout.split()
    for f in files:
        if f in SKIP or f.startswith("tests/"):
            continue
        text = (REPO_ROOT / f).read_text()
        if f.endswith(".ipynb"):   # the prose only: markdown cells
            text = "\n\n".join("".join(c["source"]) for c in json.loads(text)["cells"] if c["cell_type"] == "markdown")
        units = enumerate(text.splitlines(), 1) if f.endswith(".py") else _prose_units(text)
        for n, unit in units:
            yield f, n, unit


def test_no_retired_idea_is_presented_as_current():
    hits = [f"{f}:{n}: {why}: {unit.strip()[:140]}"
            for f, n, unit in _units() for pattern, (why, kinds) in RETIRED.items()
            if f.endswith(kinds) and re.search(pattern, unit) and not HISTORY.search(unit)]
    assert not hits, "\n".join(hits)


def test_the_check_catches_a_retired_idea_and_spares_history():
    units = [s for _, s in _prose_units("## Scoring\n\nThe cost index scores each site.\n\n"
                                        "## Every factor we ignore\n\nThe cost index.\n\n"
                                        "## Notes\n\nThe cost index was dropped in run 9.")]
    flagged = [s for s in units if re.search("cost index", s) and not HISTORY.search(s)]
    assert flagged == ["The cost index scores each site."]
