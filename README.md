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
just app     # http://localhost:8501
```

No API key or network access is required — `MODEL_BACKEND` defaults to `llm` but
automatically falls back to the deterministic `rubric` backend if
`ANTHROPIC_API_KEY` is unset.

To use the LLM backend locally, copy `.streamlit/secrets.toml.example` to
`.streamlit/secrets.toml` and set `ANTHROPIC_API_KEY`.

## Flip the decision backend

```bash
MODEL_BACKEND=rubric uv run python -m src.model.run
MODEL_BACKEND=llm uv run python -m src.model.run
```

Re-running `src.model.run` with both backends populates a comparison printed
to stdout showing where the LLM and rubric disagree.

## Perturb an assumption or a signal, live

Baseline ("reality") lives in `data/scenarios/baseline.yaml` and is computed once by
`just all`, written to `data/processed/baseline/`. With `just app` running, use the
"Build a scenario" section on the Product page to override a branch's rating, price, or
location, add a hypothetical new branch, or change `contest_ratio` — click "Run scenario"
to recompute against the fixed baseline raw data and see the diff on the map. Nothing you
do here changes baseline; "Reset to baseline" clears the session's scenario.

The existing `data/scenarios/*.yaml` files remain valid for direct CLI use:

```bash
just scenario data/scenarios/example-perturbations.yaml
```

writes `data/processed/current/diff.json` without touching the Streamlit app.

## Deploy

Push to GitHub, then on [share.streamlit.io](https://share.streamlit.io), create a new
app pointing at this repo, the branch to deploy, and `streamlit_app.py` as the main file.
If you want the optional LLM-agreement comparison on the Model page, set
`ANTHROPIC_API_KEY` in the app's Secrets panel.

## Tests

```bash
just test
```

## Known limitations

See the Model, Assumptions & Data page of the deployed app.
