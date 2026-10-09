"""How it works & limitations: docs/limitations.md, the "Market model" section of SOURCES.md, every
assumption in baseline.yaml and every scorecard / growth constant with why it was chosen."""
import re

import streamlit as st

from src.config import REPO_ROOT
from src.features.lounges import NOT_SCORED, THIN_MARKET
from src.model import growth, scorecard
from src.webapp import data
from src.webapp.views import banner, wrapped_table

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


def render() -> None:
    banner()
    st.title("How it works & limitations")
    st.markdown("We will iterate on this model: **the limitations matter more than the calls.** "
                "Below: the limitations, how the model fits together, and every assumption and "
                "threshold it uses.")
    if data.active():
        st.caption("The figures in the limitations below are at the baseline, not your what-if.")
    st.markdown(LIMITATIONS.read_text().split("\n", 1)[1])     # without its own title

    st.divider()
    st.header("How the market model fits together")
    st.markdown(section(SOURCES.read_text(), "Market model"))

    st.header("Every assumption (data/scenarios/baseline.yaml)")
    st.caption("The what-if panel on the Overview switches the three levelled assumptions and the "
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
        {"Constant": "FLIP_LOW", "Value": f"{scorecard.FLIP_LOW} of 27", "Why": scorecard.FLIP_WHY},
        {"Constant": "NEUTRAL", "Value": f"{scorecard.NEUTRAL}",
         "Why": "A missing rating gap, or capture in a thin market, scores neutral, never the worst."},
        {"Constant": "THIN_MARKET", "Value": f"{THIN_MARKET} premium salons",
         "Why": "Fewer premium salons than this: capture is a share of a tiny pool, so it is noise."},
        {"Constant": "LOW_MARGIN / HIGH_MARGIN",
         "Value": f"low within {scorecard.LOW_MARGIN} of a line; high from {scorecard.HIGH_MARGIN}",
         "Why": "Low also when the market is thin, the rating gap is missing, or the call flips "
                f"{scorecard.FLIP_LOW}+ times."},
        {"Constant": "NOT_SCORED", "Value": ", ".join(sorted(NOT_SCORED)),
         "Why": "Serves travellers, not the women in its catchment."},
    ])

    st.header("Growth areas (src/model/growth.py)")
    wrapped_table([{"Constant": k, "Value": f"{getattr(growth, k):g}" if isinstance(getattr(growth, k), float)
                    else f"{getattr(growth, k):,}", "Why": why} for k, why in growth.WHY.items()])
