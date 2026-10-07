import streamlit as st


def render() -> None:
    st.title("Why This Exists")

    st.header("The business question")
    st.markdown(
        "Bedashing Beauty Lounge operates multiple branches across Dubai. Which ones "
        "should be protected and invested in, which are fine as-is, and which are "
        "candidates for downsizing? That's the question this project answers — not with "
        "a slide deck, but with a running pipeline you can argue with."
    )

    st.header("Who this is for")
    st.markdown(
        "Software a PE firm's AI team would build for a portfolio company. It supports one "
        "conversation between three roles: Bedashing's **portfolio team** (network, real "
        "estate and expansion) uses it to form recommendations; the **COO** approves or "
        "questions them and owns branch operations and return on capital; the **PE board** "
        "has to find them defensible. So the app leads with the conclusion, every decision "
        "carries its reasons and data, and the limits (no revenue or rent data) are stated "
        "up front rather than buried."
    )

    st.header("Perturb, re-run, compare")
    st.markdown(
        "A model is only useful if you can argue with it. The core interaction here isn't "
        "'view the report' — it's change an assumption or a signal you think is wrong, "
        "rerun the same model against the changed input, and see exactly what moved: which "
        "branches flipped, by how much, and why. The report isn't a one-shot output; it's "
        "the left half of a diff whose right half you control. That's what the scenario "
        "editor on the Product page is for — not a tech demo, but sensitivity analysis, "
        "the same instinct diligence work runs on."
    )

    st.header("How this evolved")
    st.markdown(
        "- **v0** — a deliberately crude, end-to-end prototype: seed data in, a map with "
        "PROTECT/HOLD/SHRINK labels out. The point was a working toy to poke at, not a "
        "defensible model.\n"
        "- **v1** — added baseline-vs-scenario diffing: declare a baseline explicitly, "
        "perturb assumptions or signals in a hand-edited YAML file, rerun, and diff against "
        "baseline at both the branch and community level.\n"
        "- **This app** — v1's own design doc named an interactive override UI as explicit "
        "future work, deferred for later. This is that UI, built natively in Streamlit "
        "instead of a custom frontend, so perturbing a scenario is a slider, not a YAML "
        "edit.\n"
        "- **v2** — closed the brief's gaps: competitors from OpenStreetMap as a fourth "
        "signal, fixed scales and absolute thresholds instead of ranking branches into "
        "thirds, GROW/WATCH/SKIP for every community, and grounded AI explanations with "
        "units and captions on every table. The LLM decision backend was removed: the "
        "rules decide, the AI explains."
    )
