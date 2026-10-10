# Offline path (no API key; how the committed cache was written, in a Claude Code session):
#   uv run python -m src.explain prompts DIR   # one prompt per subject missing from the cache
#   # write each answer to the DIR/answers/<file> named in its prompt
#   uv run python -m src.explain check DIR     # verify the answers, write nothing
#   uv run python -m src.explain ingest DIR    # verify again and cache the grounded ones
# NOT SCORED lounges and SKIP areas keep their template. Commit the cache after either path.

# Regenerate the committed AI explanation cache via the Anthropic API (needs ANTHROPIC_API_KEY)
explain:
    uv run python -m src.explain

# Launch the Streamlit app on http://localhost:8501
app:
    uv run streamlit run streamlit_app.py

# Open the notebooks in JupyterLab, starting at the scorecard and growth decisions
notebook:
    uv run --extra notebook jupyter lab notebooks/decisions.ipynb

test:
    uv run --extra dev --extra notebook pytest

# Print every lounge and growth-area call at the baseline as CSV (e.g. just labels > labels.csv)
labels:
    @uv run python -c "import csv, sys; from src.baseline import run; r = run(); w = csv.writer(sys.stdout); w.writerow(['kind', 'id', 'action', 'confidence', 'composite']); w.writerows(('lounge', d.branch_id, d.action, d.confidence, round(d.composite, 3)) for d in r.decisions); w.writerows(('area', d.area_id, d.action, '', '') for d in r.area_decisions)"
