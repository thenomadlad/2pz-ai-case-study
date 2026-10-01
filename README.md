# Bedashing V0

A deliberately crude, end-to-end prototype for exploring retail branch decisions
for Bedashing Beauty Lounge (Dubai only). See
`docs/designs/v0.md` for the full design, architecture, and build history.

## Setup

```bash
uv sync --extra dev
```

## Run everything

```bash
just all     # stages 1-3: acquire -> features -> model
just serve   # http://localhost:8000
```

No API key or network access is required — `MODEL_BACKEND` defaults to `llm` but
automatically falls back to the deterministic `rubric` backend if
`ANTHROPIC_API_KEY` is unset.

To use the LLM backend, copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`.

## Flip the decision backend

```bash
MODEL_BACKEND=rubric uv run python -m src.model.run
MODEL_BACKEND=llm uv run python -m src.model.run
```

Re-running `src.model.run` with both backends populates a comparison printed
to stdout showing where the LLM and rubric disagree.

## Tests

```bash
just test
```

## Known limitations

See §9 of the design doc, and the "Assumptions" toggle on the map itself:

1. Nearest-branch assignment ignores travel time, malls, parking, habit, price, brand.
2. Community centroids collapse large communities to a single point.
3. No competitor data — the single biggest omission.
4. Female population is a poor demand proxy on its own.
5. No revenue, footfall, staffing, or lease data.
6. LLM labels have no ground truth; agreement with the rubric is a sanity check, not validation.
7. Prices are a thin, possibly-stale basket.
8. Dubai only.
