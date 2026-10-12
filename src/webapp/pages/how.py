"""README page: the README, docs/model.md and docs/implementation.md themselves (one source
of truth; Mermaid diagrams drawn in the browser, links between the three as in-page anchors, other repo
links pointed at GitHub), then live tables of every assumption in baseline.yaml and every
scorecard / growth constant with why it was chosen."""
import html
import posixpath
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
from src.model import growth, scorecard, served
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


README = REPO_ROOT / "README.md"
# The page, in order: each file's in-app anchor is its title's heading slug, so links between them stay in the page
# Full page URLs, not bare "#..." anchors: Streamlit doesn't scroll on an in-page anchor click, but it does
# land on the heading when a page loads with one
DOCS = {"README.md": "/how#bedashing-network-right-sizing", "docs/model.md": "/how#the-model-in-detail",
        "docs/implementation.md": "/how#implementation-notes"}
REPO_URL = "https://github.com/thenomadlad/2pz-ai-case-study/blob/main/"
_MERMAID = """<div class="mermaid">{code}</div>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<script>mermaid.initialize({{startOnLoad: true, theme: "neutral", securityLevel: "strict"}});</script>"""


def _link(path: str, base: str) -> str:
    """A repo-relative link from a file in `base`: an in-page anchor for the docs on this page, else GitHub."""
    target = posixpath.normpath(posixpath.join(base, path))
    return DOCS.get(target, REPO_URL + target)


def readme_parts(text: str, base: str = "") -> list[tuple[str, str]]:
    """A doc as ("md", markdown) and ("mermaid", diagram) parts, its repo-relative links (relative to the
    directory `base`) rewritten by _link so they work inside the app."""
    text = re.sub(r"\]\((?!https?://|#|mailto:)([^)\s]+)\)", lambda m: f"]({_link(m.group(1), base)})", text)
    parts = re.split(r"^```mermaid\n(.*?)^```\n?", text, flags=re.DOTALL | re.MULTILINE)
    return [("mermaid" if i % 2 else "md", p) for i, p in enumerate(parts) if p.strip()]


def render() -> None:
    # The README and the two docs are this page: one source of truth for the model, its limitations and trade-offs
    for doc in DOCS:
        for kind, part in readme_parts((REPO_ROOT / doc).read_text(), posixpath.dirname(doc)):
            if kind == "md":
                st.markdown(part)
            else:
                # st.iframe (components.v1.html is deprecated): this HTML is our own committed diagram, not
                # user input; height grows with the diagram's size so a small chain doesn't leave a gap
                st.iframe(_MERMAID.format(code=html.escape(part)), height=max(150, min(760, 40 + 11 * part.count("\n"))))

    st.divider()
    st.header("Live values from the code")
    st.caption("Read from the code and data/scenarios/baseline.yaml each time the page loads, so they can't go stale.")
    st.subheader("Every assumption (data/scenarios/baseline.yaml)")
    st.caption("The What-if explorer switches the four levelled assumptions and the "
               "search recall.")
    notes = yaml_notes(data.BASELINE_YAML.read_text())
    wrapped_table([{"Assumption": k, "Value (levels)": _fmt(v),
                    "Why / source": notes.get(k) or "See the row above."}
                   for k, v in data.assumptions().model_dump().items()])

    st.subheader("Lounge scorecard (src/model/scorecard.py)")
    wrapped_table([{"Signal": s.label, "Scale": f"{s.worst:g} → 0, {s.best:g} → 1", "Weight": f"{s.weight:g}",
                    "Why": s.why} for s in scorecard.SIGNALS])
    wrapped_table([
        {"Constant": "PROTECT_AT / SHRINK_AT", "Value": f"{scorecard.PROTECT_AT} / {scorecard.SHRINK_AT}",
         "Why": scorecard.THRESHOLDS_WHY},
        {"Constant": "FLIP_LOW_SHARE", "Value": f"a third: {scorecard.FLIP_LOW} of {scorecard.COMBOS} ({', '.join(scorecard.LIVE_AXES)})",
         "Why": scorecard.FLIP_WHY},
        {"Constant": "Drive time and coverage in the Huff split (src/model/served.py)",
         "Value": " · ".join(f"{m} min: " + "/".join(f"{w:.2f}" for w in served.decay(m).values()) for m in (10, 15, 20))
         + " (10/15/20-min band weights); competitors ×" + " / ×".join(
             f"{served.competitor_scale(c):.2f}" for c in data.assumptions().competitor_coverage.values()),
         "Why": served.LEVELS_WHY},
        {"Constant": "NEUTRAL", "Value": f"{scorecard.NEUTRAL}",
         "Why": "A missing signal value (e.g. no shop rent) scores neutral, never the worst."},
        {"Constant": "WEIGHT_STEPS", "Value": " / ".join(f"×{x:g}" for x in scorecard.WEIGHT_STEPS),
         "Why": scorecard.WEIGHT_WHY},
        {"Constant": "LOW_MARGIN / HIGH_MARGIN",
         "Value": f"low within {scorecard.LOW_MARGIN} of a line; high from {scorecard.HIGH_MARGIN}",
         "Why": f"Low also when the call flips in {scorecard.FLIP_LOW}+ assumption combinations or a signal weight ±25% changes it."},
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

    st.subheader("Growth areas (src/model/growth.py)")
    wrapped_table([{"Constant": k, "Value": _const(getattr(growth, k)), "Why": why} for k, why in growth.WHY.items()])
