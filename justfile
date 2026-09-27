# Stages 1-3: acquire -> features -> model. Default recipe.
all:
    uv run python -m src.acquire.run
    uv run python -m src.features.build
    uv run python -m src.model.run

# Serve the JSON API + Leaflet frontend on http://localhost:8000
serve:
    uv run uvicorn src.serve.app:app --reload --port 8000

# Wipe generated data. Never touches data/seed.
clean:
    rm -rf data/raw/* data/processed/*
    touch data/raw/.gitkeep data/processed/.gitkeep

test:
    uv run pytest
