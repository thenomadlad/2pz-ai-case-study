.PHONY: all serve clean test

all:
	uv run python -m src.acquire.run
	uv run python -m src.features.build
	uv run python -m src.model.run

serve:
	uv run uvicorn src.serve.app:app --reload --port 8000

clean:
	rm -rf data/raw/* data/processed/*
	touch data/raw/.gitkeep data/processed/.gitkeep

test:
	uv run pytest
