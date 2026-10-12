"""How it works & limitations: docs/limitations.md, the "Market model" section of SOURCES.md, every
assumption in baseline.yaml and every scorecard / growth constant with why it was chosen."""
import re

import streamlit as st

from src.config import REPO_ROOT
from src.features.lounges import (
    MIN_REF_SITES,
    NOT_SCORED,
    NOT_SCORED_WHY,
    SITE_REFERENCE_WHY,
    site_reference,
)
from src.model import growth, scorecard
from src.webapp import data
from src.webapp.views import wrapped_table

LIMITATIONS = REPO_ROOT / "docs" / "limitations.md"
SOURCES = REPO_ROOT / "data" / "seed" / "v3" / "SOURCES.md"


def section(markdown: str, heading: str) -> str:
    """The body of the `## heading...` section."""
    m = re.search(rf"^## {re.escape(heading)}.*?\n(.*?)(?=^## |\Z)", markdown, re.DOTALL | re.MULTILINE)
    return m.group(1).strip() if m else ""


def yaml_notes(text: str) -> dict[str, str]:
    """The comments above each top-level assumption and beside its levels, from baseline.yaml."""
    notes, pending, key = {}, [], None
    for line in text.splitlines():
        s = line.strip()
        if s and not line[0].isspace() and not s.startswith("#"):
            pending = []
        if s.startswith("#"):
            pending.append(s.lstrip("# "))
        elif m := re.match(r"^  (\w+):", line):
            key, notes[m.group(1)], pending = m.group(1), " ".join(pending), []
        elif key and (m := re.match(r"^\s{4,}(\w+):.*?#\s*(.*)", line)):
            notes[key] += f" {m.group(1)}: {m.group(2)}."
    return notes


def _fmt(v) -> str:
    if isinstance(v, dict):
        return " · ".join(f"{k}: {x}" for k, x in v.items())
    return ", ".join(v) if isinstance(v, list) else str(v)


def _const(v) -> str:
    return f"{v:g}" if isinstance(v, float) else f"{v:,}" if isinstance(v, int) else getattr(v, "pattern", str(v))


def render() -> None:
    st.title("How it works & limitations")
    st.markdown("We will iterate on this model: **the limitations matter more than the calls.** "
                "Below: the limitations, how the model fits together, and every assumption and "
                "threshold it uses.")
    st.markdown(LIMITATIONS.read_text().split("\n", 1)[1])     # without its own title

    st.divider()
    st.header("How the market model fits together")
    st.markdown(section(SOURCES.read_text(), "Market model"))

    st.header("Every assumption (data/scenarios/baseline.yaml)")
    st.caption("The What-if explorer switches the four levelled assumptions and the "
               "search recall.")
    notes = yaml_notes(data.BASELINE_YAML.read_text())
    wrapped_table([{"Assumption": k, "Value (levels)": _fmt(v),
                    "Why / source": notes.get(k) or "See the row above."}
                   for k, v in data.assumptions().model_dump().items()])

    st.header("Lounge scorecard (src/model/scorecard.py)")
    wrapped_table([{"Signal": s.label, "Scale": f"{s.worst:g} → 0, {s.best:g} → 1", "Weight": f"{s.weight:g}",
                    "Why": s.why} for s in scorecard.SIGNALS])
    wrapped_table([
        {"Constant": "PROTECT_AT / SHRINK_AT", "Value": f"{scorecard.PROTECT_AT} / {scorecard.SHRINK_AT}",
         "Why": scorecard.THRESHOLDS_WHY},
        {"Constant": "FLIP_LOW_SHARE", "Value": f"a third: {scorecard.FLIP_LOW} of {scorecard.COMBOS}",
         "Why": scorecard.FLIP_WHY},
        {"Constant": "NEUTRAL", "Value": f"{scorecard.NEUTRAL}",
         "Why": "A missing signal value (e.g. no shop rent) scores neutral, never the worst."},
        {"Constant": "WEIGHT_STEPS", "Value": " / ".join(f"×{x:g}" for x in scorecard.WEIGHT_STEPS),
         "Why": scorecard.WEIGHT_WHY},
        {"Constant": "LOW_MARGIN / HIGH_MARGIN",
         "Value": f"low within {scorecard.LOW_MARGIN} of a line; high from {scorecard.HIGH_MARGIN}",
         "Why": f"Low also when the call flips {scorecard.FLIP_LOW}+ times or a signal weight ±25% changes it."},
        {"Constant": "Site reference (src/features/lounges.py)",
         "Value": " · ".join(f"{e}: {n}" for e, n in site_reference().emirate.value_counts().items())
         + f" salon sites; under {MIN_REF_SITES}: demand ranked UAE-wide", "Why": SITE_REFERENCE_WHY},
        {"Constant": "RENT_RATIO_P10 / P90", "Value": f"{scorecard.RENT_RATIO_P10:g} / {scorecard.RENT_RATIO_P90:g}",
         "Why": scorecard.RENT_RATIO_WHY},
        {"Constant": "performance_vs_site", "Value": "served women ÷ site served",
         "Why": "Context, not scored: 'The model estimates this lounge is performing 2.7x compared to its site' "
                "(khalifa-city-a at baseline). The call scores the site; this says how the lounge does on it, "
                "which rests on its own reviews and rating."},
        {"Constant": "NOT_SCORED", "Value": ", ".join(sorted(NOT_SCORED)), "Why": NOT_SCORED_WHY},
    ])

    st.header("Growth areas (src/model/growth.py)")
    wrapped_table([{"Constant": k, "Value": _const(getattr(growth, k)), "Why": why} for k, why in growth.WHY.items()])
