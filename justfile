# Generate grounded AI explanations for the baseline through the Anthropic API (needs
# ANTHROPIC_API_KEY in .env) and write the committed cache data/explanations/cache.json.
# Commit the result. NOT SCORED lounges and SKIP areas keep their template.
#
# Offline path (no API key; how the committed cache was written, in a Claude Code session):
#   uv run python -m src.explain prompts DIR   # one prompt per subject missing from the cache
#   # write each answer to the DIR/answers/<file> named in its prompt
#   uv run python -m src.explain check DIR     # verify the answers, write nothing
#   uv run python -m src.explain ingest DIR    # verify again and cache the grounded ones
explain:
    uv run python -m src.explain

# Launch the Streamlit app on http://localhost:8501
app:
    uv run streamlit run streamlit_app.py

# Wipe data/raw: the fetch scripts' API response caches and the WorldPop / OSM downloads.
# Re-fetching costs Google Places and Mapbox quota. Never touches data/seed or data/scenarios.
clean:
    rm -rf data/raw/*
    touch data/raw/.gitkeep

# Open the notebooks in JupyterLab, starting at the scorecard and growth decisions
notebook:
    uv run --extra notebook jupyter lab notebooks/decisions.ipynb

test:
    uv run --extra dev --extra notebook pytest
