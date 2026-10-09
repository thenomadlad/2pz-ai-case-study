# Stages 1-3: acquire -> features -> model, using data/scenarios/baseline.yaml's
# assumptions. Writes data/raw/*.json and data/processed/baseline/*.json.
all:
    uv run python -m src.scenario.baseline

# Generate grounded AI explanations for the baseline (needs ANTHROPIC_API_KEY in .env)
# and write
# the committed cache data/explanations/cache.json. Commit the result.
explain:
    uv run python -m src.explain

# Launch the Streamlit app on http://localhost:8501
app:
    uv run streamlit run streamlit_app.py

# Run a scenario: apply its overrides on top of the fixed baseline raw data,
# recompute features+model, diff against data/processed/baseline/, write
# data/processed/current/*.json including diff.json.
# Example: just scenario data/scenarios/example-perturbations.yaml
scenario SCENARIO:
    uv run python -m src.scenario.run {{SCENARIO}}

# Wipe generated data. Never touches data/seed or data/scenarios.
clean:
    rm -rf data/raw/* data/processed/*
    touch data/raw/.gitkeep data/processed/.gitkeep

# Open the data-vetting notebook in JupyterLab
notebook:
    uv run --extra notebook jupyter lab notebooks/branches.ipynb

test:
    uv run --extra dev pytest
