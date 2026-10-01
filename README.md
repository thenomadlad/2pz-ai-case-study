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

## Perturb an assumption or a signal (v1)

Baseline ("reality") lives in `data/scenarios/baseline.yaml` and is computed once by
`just all`, written to `data/processed/baseline/`. A scenario is a YAML file under
`data/scenarios/` declaring assumption overrides (`contest_ratio`, `model_backend`) and/or
signal overrides on specific branches/communities (including relocating a branch, changing
its rating, or introducing a hypothetical new branch). Baseline never changes as a result of
running a scenario -- there is no "promote" step.

```bash
just scenario data/scenarios/example-perturbations.yaml
```

Writes `data/processed/current/` plus a `diff.json` comparing it against baseline. With
`just serve` running, the map's "Diff vs baseline" toggle (enabled once a scenario has run)
highlights branches whose PROTECT/HOLD/SHRINK action or feature values changed, and
communities that got reassigned to a different nearest branch.

See `docs/designs/v1.md` for the full design, including what's explicitly out of scope for
this version (capacity, re-running `acquire` per scenario, an interactive override UI).

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
