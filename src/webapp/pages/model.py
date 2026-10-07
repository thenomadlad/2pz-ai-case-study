import streamlit as st

from src import explain
from src.config import settings
from src.model import opportunity, rubric
from src.webapp.data import load_baseline

KNOWN_LIMITATIONS = [
    ("Nearest-branch assignment is false. Real choice depends on travel time, malls, "
     "parking, habit, price and brand. Straight-line distance from a community centroid "
     "ignores all of it."),
    ("Community centroids are not where people live. Large communities get collapsed to "
     "a point."),
    ("Competitors come from OpenStreetMap, which misses salons, so competitor counts are "
     "a lower bound. Gents' salons are filtered out by tag and by name, imperfectly."),
    ("Female population is a poor demand proxy on its own — and every value in this "
     "dataset is an estimate (see Data provenance below), not just a proxy that could be "
     "refined."),
    ("No revenue, footfall, staffing or lease data, so 'SHRINK' here cannot distinguish a "
     "badly-located branch from a well-located, badly-run one."),
    ("The AI only explains decisions; it never makes them. Its numbers are checked against "
     "the data, but its wording can still over- or under-state how strong a signal is."),
    ("Thresholds and scale anchors are judgement calls picked from the Dubai data "
     "distribution, not fitted to outcomes. There are no outcomes to fit to."),
    ("Prices are not 'a thin basket that may not be current' — there are zero real "
     "per-branch prices anywhere, confirmed, not merely unsourced."),
    "Dubai only, by design: 9 of Bedashing's 23 UAE branches.",
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
        "distance) and every competitor salon to its nearest community, then rolls that up "
        "into per-branch features (female residents served, cannibalisation, competitors "
        "per 10k women, sibling proximity) and per-community features.\n"
        "- **Model**: a deterministic rubric scores each branch on four fixed scales and "
        "applies absolute thresholds (PROTECT / HOLD / SHRINK); a two-question 2x2 labels "
        "each community GROW / WATCH / SKIP.\n"
        "- **Explain**: Claude writes 3 reasons with 2-3 data points each, plus a caption "
        "for the factor table, and every number is checked against the data.\n"
    )


def _render_scales() -> None:
    st.header("Scales and thresholds")
    st.markdown("Each branch signal is scored 0-1 on a **fixed** scale, so a branch's score "
                "doesn't move just because a sibling changed.")
    st.table({
        "Signal": [s.label for s in rubric.SIGNALS],
        "Scores 0 at": [f"{s.worst:g}" for s in rubric.SIGNALS],
        "Scores 1 at": [f"{s.best:g}" for s in rubric.SIGNALS],
        "Why this scale": [s.why for s in rubric.SIGNALS],
    })
    st.markdown(f"**Branch thresholds.** {rubric.THRESHOLDS_WHY}")
    st.markdown(f"**Opportunity thresholds.** {opportunity.THRESHOLDS_WHY}")
    with st.expander("Glossary: every factor shown in the app"):
        st.dataframe([{"Factor": f.label, "Unit": f.unit, "What it means": f.meaning}
                      for f in explain.GLOSSARY.values()], hide_index=True,
                     width="stretch")


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
        "population is estimated via a global 49% share and flagged as such.\n\n"
        f"**{len(data.competitors)} competitor salons** from OpenStreetMap (`shop=beauty` and "
        "`shop=hairdresser` around Dubai, gents' salons and Bedashing itself removed), pulled "
        "once by `scripts/fetch_competitors.py` and committed. Each counts toward the nearest "
        "community within 3 km."
    )
    st.caption(f"Configured data sources: branches={data.data_sources['branches']}, "
               f"communities={data.data_sources['communities']}, "
               f"competitors={data.data_sources['competitors']}")


def _render_ai_layer() -> None:
    st.header("How the AI layer works")
    cache = explain.load_cache()
    st.markdown(
        "The rules make every decision. Claude explains them for the portfolio team: 3 "
        "reasons, each backed by 2-3 data points copied from the decision's fact sheet, plus "
        "a plain-language caption for the factor table.\n\n"
        "**Grounding check.** Every cited field must exist in the fact sheet with the same "
        "value, and every number in the prose must match a fact or a published threshold. "
        "A failed check is retried once with the errors fed back, then replaced by a "
        "template explanation.\n\n"
        "**No key needed to see it.** Explanations for the baseline are generated once "
        "(`just explain`) and committed, keyed by a hash of the exact numbers. A scenario "
        "that changes a branch's numbers gets a live explanation if a key is configured, "
        "otherwise the template, clearly labelled."
    )
    st.caption(f"{len(cache)} AI explanations committed in data/explanations/cache.json.")


def _render_limitations() -> None:
    st.header("Known limitations")
    for item in KNOWN_LIMITATIONS:
        st.markdown(f"- {item}")


def render() -> None:
    st.title("Model, Assumptions & Data")
    data = load_baseline(settings)
    _render_pipeline()
    _render_scales()
    _render_data_provenance(data)
    _render_ai_layer()
    _render_limitations()
