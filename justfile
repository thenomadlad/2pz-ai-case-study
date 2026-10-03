# Stages 1-3: acquire -> features -> model, using data/scenarios/baseline.yaml's
# assumptions. Writes data/raw/*.json and data/processed/baseline/*.json.
all:
    uv run python -m src.scenario.baseline

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

test:
    uv run pytest
