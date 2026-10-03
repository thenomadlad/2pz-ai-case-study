import streamlit as st

from src.config import settings
from src.webapp.data import load_baseline

KNOWN_LIMITATIONS = [
    ("Nearest-branch assignment is false. Real choice depends on travel time, malls, "
     "parking, habit, price and brand. Straight-line distance from a community centroid "
     "ignores all of it."),
    ("Community centroids are not where people live. Large communities get collapsed to "
     "a point."),
    ("No competitors. A branch with five rival salons next door looks identical to one "
     "with none. The single biggest omission."),
    ("Female population is a poor demand proxy on its own — and every value in this "
     "dataset is an estimate (see Data provenance below), not just a proxy that could be "
     "refined."),
    ("No revenue, footfall, staffing or lease data, so 'SHRINK' here cannot distinguish a "
     "badly-located branch from a well-located, badly-run one."),
    ("The LLM classifies without ground truth and will produce confident-sounding labels "
     "regardless. Agreement with the rubric is a sanity check, not validation."),
    ("Prices are not 'a thin basket that may not be current' — there are zero real "
     "per-branch prices anywhere, confirmed, not merely unsourced."),
    "Dubai only.",
]


def _render_pipeline() -> None:
    st.header("The pipeline")
    st.markdown(
        "Four independently re-runnable, file-based stages:\n\n"
        "`seed data -> acquire -> raw JSON -> features -> processed JSON -> model -> "
        "decisions`\n\n"
        "- **Acquire**: loads branch/community/price seed data, falling back to seed "
        "whenever live enrichment isn't available (it never is in this build — see Data "
        "provenance below).\n"
        "- **Features**: assigns every community to its nearest branch (haversine "
        "distance), rolls that up into per-branch features (population served, contested "
        "share, price index, sibling proximity) plus network-wide medians to compare "
        "against.\n"
        "- **Model**: a deterministic rubric (normalize population/contested-share/rating, "
        "equal-weight sum, top third PROTECT / bottom third SHRINK / rest HOLD) or an LLM "
        "backend (one Anthropic tool-use call per branch, disk-cached, rubric fallback on "
        "failure) label each branch.\n"
    )


def _render_data_provenance(data) -> None:
    st.header("Data provenance")
    st.markdown(
        "**9 real Dubai branches** (2GIS's UAE branch-aggregation page for ratings/reviews). "
        "**50 real Dubai communities**, population from the Dubai Statistics Center 2022/2024 "
        "Population Bulletin.\n\n"
        "**Every `avg_price_aed` is estimated.** No source checked (2GIS, Fresha, Groupon, "
        "social media, including a real browser rendering Fresha's pages directly) exposes a "
        "per-branch price for any of the 9 real branches. All 9 carry a single fallback "
        "constant (AED 99 — the one real Bedashing price point found anywhere, a chain-wide "
        "promo) and are flagged estimated.\n\n"
        "**Every `population_female` is estimated.** `dubaipulse.gov.ae` and `dsc.gov.ae` "
        "both block automated access, and the source Population Bulletin PDF doesn't publish "
        "a per-community gender split at all — only emirate-wide. All 50 communities' female "
        "population is estimated via a global 49% share and flagged as such."
    )
    st.caption(f"Configured data sources: branches={data.data_sources['branches']}, "
               f"communities={data.data_sources['communities']}")


def _render_backend_comparison() -> None:
    st.header("Rubric vs. LLM")
    if settings.anthropic_api_key:
        st.info("ANTHROPIC_API_KEY is configured — live rubric-vs-LLM agreement would run "
                "here in a future iteration.")
    else:
        st.markdown(
            "This public demo runs the **rubric backend only** — free, instant, "
            "deterministic, and exactly reproducible. The LLM backend is a real, working "
            "alternative (one Anthropic call per branch, structured output, disk-cached) "
            "but isn't exposed publicly here since it costs real API calls and its cache "
            "never helps across different scenarios."
        )


def _render_limitations() -> None:
    st.header("Known limitations")
    for item in KNOWN_LIMITATIONS:
        st.markdown(f"- {item}")


def render() -> None:
    st.title("Model, Assumptions & Data")
    data = load_baseline(settings)
    _render_pipeline()
    _render_data_provenance(data)
    _render_backend_comparison()
    _render_limitations()
