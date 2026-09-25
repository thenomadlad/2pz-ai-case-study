# Bedashing V0 — scrappy branch right-sizing prototype

Date: 2026-09-24

This supersedes the earlier generic-scaffold spec for this repo. The case
study content is now known, and it comes with its own complete design —
this document is that design, adapted to fit the `2pz-ai-case-study` repo
we already created. The only adaptation: the source doc's illustrative
`bedashing-v0/` repo root is dropped and the layout below starts directly
at this repo's root instead of a nested subfolder.

## 0. What this is, and what it is not

A deliberately crude, end-to-end prototype for exploring retail branch
decisions for Bedashing Beauty Lounge (a multi-branch salon chain in the
UAE). The point is a working toy you can poke at within a day — not a
defensible model.

It is known to be wrong in ways listed in §9. Build it anyway; the value is
having something concrete to argue with. Do not add sophistication that
isn't in this doc.

One-sentence behaviour: given branch locations, Dubai community population
(female), and prices, assign each community to its nearest branch, roll
that up into per-branch features, ask an LLM to label each branch
PROTECT / HOLD / SHRINK with reasons, and render it all on a Leaflet map.

Non-goals for V0: isochrones, competitors, Huff/gravity models,
authentication, a database, tests beyond smoke tests, deployment, mobile
layout, Abu Dhabi/Sharjah (Dubai only).

## 1. Principles the implementation must follow

1. File-based pipeline. Each stage reads files and writes files to
   `data/`. No database, no in-memory coupling. Every intermediate
   artifact is human-readable JSON/CSV so it can be opened and argued
   with.
2. Each stage is independently re-runnable and idempotent. Re-running
   stage 3 must not require re-running stage 1.
3. It must run with zero network access and zero API keys. Committed seed
   data in `data/seed/` is the primary path; scrapers and APIs are
   enrichment, always optional, always falling back to seed. A first-time
   user runs `make all` and gets a working map.
4. The decision model sits behind an interface with two implementations
   (LLM and a deterministic rubric) so they can be compared. See §6.
5. Scrappy means small, not sloppy. Type hints, dataclasses or pydantic
   models for the stage boundaries, and a `README.md`. No frameworks
   beyond what's listed.

## 2. Stack

- Python 3.11+, `uv`
- `httpx`, `pydantic`, `python-dotenv`
- `fastapi` + `uvicorn` for serving
- Frontend: plain HTML + vanilla JS + Leaflet from CDN. No React, no
  bundler, no build step.
- LLM: Anthropic API via the `anthropic` SDK. Model configurable via env;
  default to a fast/cheap one.

Deliberately avoided: geopandas/shapely (heavy install, not needed —
haversine on centroids is enough for V0), any map library requiring a
token if avoidable (Leaflet + OpenStreetMap tiles need none).

## 3. Repo layout

```
2pz-ai-case-study/
  Makefile
  pyproject.toml
  uv.lock
  .env.example
  README.md
  data/
    seed/
      branches.csv            # committed, hand-curated — the guaranteed path
      communities.csv         # committed, hand-curated
    raw/                      # gitignored, written by stage 1
    processed/                # gitignored, written by stages 2-3
      branch_features.json
      community_assignment.json
      decisions.json
  src/
    config.py
    models.py                 # pydantic models for every stage boundary
    acquire/
      __init__.py
      branches.py
      population.py
      prices.py
      run.py                  # stage 1 entrypoint
    features/
      assign.py               # nearest-branch assignment
      build.py                # stage 2 entrypoint
    model/
      base.py                 # DecisionModel protocol
      llm.py                  # LLM implementation
      rubric.py                # deterministic implementation
      run.py                  # stage 3 entrypoint
    serve/
      app.py                  # FastAPI
      static/
        index.html
        app.js
        style.css
  docs/
    superpowers/specs/        # design specs (this file)
```

`pyproject.toml` + `uv.lock` replace the source doc's
`requirements.txt` — same role, this repo already standardized on `uv`.

## 4. Stage 1 — data acquisition (`src/acquire/`)

Writes to `data/raw/`. Every module exposes `load() -> list[Model]` which
tries live sources, falls back to seed, and logs loudly which one it used.

### 4.1 Branches (`branches.py`)

Target output — `data/raw/branches.json`, list of:

```python
class Branch(BaseModel):
    id: str              # slug, e.g. "al-barsha"
    name: str
    lat: float
    lng: float
    area: str            # community/neighbourhood name as written on the source
    rating: float | None
    review_count: int | None
    avg_price_aed: float | None
    source: str          # "seed" | "fresha" | "places"
```

Sources, in priority order:

1. Seed CSV (primary). `data/seed/branches.csv`, hand-curated. Populate it
   from `bedashingbeauty.com/our-locations` and Fresha listings. Dubai
   branches only for V0. Aim for whatever exists — expect roughly 10-20
   Dubai locations. Geocode by hand (paste coordinates from a map) rather
   than writing a geocoder.
2. Optional enrichment if `ENABLE_SCRAPE=1`: fetch the public locations
   page and/or Fresha venue pages to refresh ratings and price points. Use
   `httpx` with a normal User-Agent, one request per second, and cache
   responses in `data/raw/cache/`. If any request fails, log and continue
   with seed values — never crash the pipeline.

Note for whoever runs this: check the terms of service of any site before
enabling scraping. Default is off.

### 4.2 Population (`population.py`)

Target output — `data/raw/communities.json`, list of:

```python
class Community(BaseModel):
    id: str
    name_en: str
    lat: float           # centroid
    lng: float
    population_total: int
    population_female: int | None   # None -> estimated, see below
    is_estimated: bool
```

Sources:

1. Seed CSV (primary). `data/seed/communities.csv`, built from Dubai
   Statistics Center figures (Dubai Pulse dataset
   `dsc_population_by_community`, and the DSC Population Bulletin PDF).
   Use community centroids — approximate ones typed by hand are fine for
   V0. Target ~30-60 communities covering the populated parts of Dubai; do
   not attempt all 226.
2. Optional: if `DUBAI_PULSE_ENABLED=1`, hit the Dubai Pulse open API for
   the same dataset and merge. Registration may be required; treat failure
   as normal and fall back.

Female population handling — this is the most important line in this
stage. If a community has no gender split, estimate it by applying a
global female share and set `is_estimated=True`. The UI must visually
distinguish estimated from reported values. Do not silently impute.

### 4.3 Prices (`prices.py`)

`avg_price_aed` per branch: a representative ticket. For V0 take a fixed
basket of 3-4 services (e.g. blow-dry, manicure, pedicure) and average the
branch's listed prices for them. Seed it by hand; enrichment optional. If
a branch has no price, use the network median and flag it.

### 4.4 Stage entrypoint

`python -m src.acquire.run` — runs all three, writes `data/raw/*.json`,
prints a summary table: source used per dataset, record counts, and a
count of estimated/imputed fields.

## 5. Stage 2 — feature builder (`src/features/`)

Reads `data/raw/`, writes `data/processed/branch_features.json` and
`data/processed/community_assignment.json`.

### 5.1 Assignment rule

The stated assumption: every resident uses her nearest branch. For each
community centroid, compute haversine distance to every branch. Assign
the community's entire female population to the nearest one.

Also record the second nearest branch and its distance — this is what
makes overlap visible without any catchment geometry.

```python
class CommunityAssignment(BaseModel):
    community_id: str
    nearest_branch_id: str
    nearest_km: float
    second_branch_id: str | None
    second_km: float | None
    contested: bool          # second_km / nearest_km < CONTEST_RATIO (default 1.25)
    female_pop: int
```

### 5.2 Per-branch features

```python
class BranchFeatures(BaseModel):
    branch_id: str
    name: str
    lat: float
    lng: float
    female_pop_served: int
    communities_served: int
    mean_distance_km: float          # pop-weighted
    max_distance_km: float
    contested_pop: int               # female pop in contested communities
    contested_share: float           # contested_pop / female_pop_served
    nearest_sibling_km: float        # distance to closest other Bedashing branch
    siblings_within_5km: int
    avg_price_aed: float
    price_index: float               # avg_price / network median price
    rating: float | None
    review_count: int | None
    pop_per_1k_rank: int             # rank within network by female_pop_served
    estimated_fields: list[str]      # names of fields derived from imputed inputs
```

### 5.3 Network context

Also emit a `network` object in `branch_features.json`: median / p25 / p75
for `female_pop_served`, `contested_share`, `avg_price_aed`, `rating`,
plus branch count and total female population covered. The decision model
needs this to have any sense of scale — without it, "serves 40,000 women"
means nothing.

Entrypoint: `python -m src.features.build`.

## 6. Stage 3 — decision model (`src/model/`)

### 6.1 Interface

```python
class Decision(BaseModel):
    branch_id: str
    action: Literal["PROTECT", "HOLD", "SHRINK"]
    confidence: Literal["low", "medium", "high"]
    rationale: str               # 1-2 sentences
    key_drivers: list[str]       # 2-4 feature names that mattered most
    caveats: list[str]           # what the model couldn't see

class DecisionModel(Protocol):
    name: str
    def decide(self, branch: BranchFeatures, network: NetworkStats) -> Decision: ...
```

Selected via `MODEL_BACKEND=llm|rubric` (default `llm`).

### 6.2 LLM implementation (`llm.py`)

One call per branch. Temperature 0. Structured output enforced by the
`Decision` schema (use tool-use / JSON mode, not free-text parsing).

Prompt structure:

- System: "You are a retail portfolio analyst for a UAE salon chain. You
  classify branches as PROTECT, HOLD or SHRINK. You only reason from the
  numbers provided. You never invent data. If the evidence is thin you
  say so in `caveats` and lower `confidence`."
- User: definitions of each action; the network context block; this
  branch's feature block as JSON; an explicit list of what the model does
  NOT know (no revenue, no footfall, no staffing, no competitors, no
  lease costs).

Cache by SHA of (prompt template version, feature vector, model name) in
`data/processed/.llm_cache/`. Re-running without feature changes must
make zero API calls and complete instantly.

If `ANTHROPIC_API_KEY` is absent, log a warning and automatically fall
back to the rubric backend so the app still runs end-to-end.

Default model: a fast/cheap current model (e.g. Haiku), overridable via
`ANTHROPIC_MODEL`.

### 6.3 Rubric implementation (`rubric.py`)

A deliberately simple transparent baseline, ~30 lines. Score each branch
on normalized `female_pop_served` (higher better), `contested_share`
(higher worse), `rating` (higher better). Sum with equal weights. Top
third PROTECT, bottom third SHRINK, rest HOLD. `key_drivers` = the two
features furthest from the network median.

Why this exists: so you can flip `MODEL_BACKEND` and see where the LLM
disagrees with dumb arithmetic. Where they agree, the LLM added nothing.
Where they disagree, one of them is interesting. This comparison is the
actual experiment.

Entrypoint: `python -m src.model.run` → `data/processed/decisions.json`.
Print a confusion table of llm-vs-rubric when both cached results exist.

## 7. Stage 4 — service (`src/serve/app.py`)

FastAPI, reads the processed JSON at startup (and on each request in dev,
so edits show up on refresh).

Endpoints:

- `GET /` → `static/index.html`
- `GET /api/branches` → branch features joined with decisions
- `GET /api/communities` → community assignment joined with centroid +
  population
- `GET /api/network` → network stats + metadata (which model backend,
  which data sources, when the pipeline last ran)
- `GET /api/health`

CORS open (localhost only anyway). Run with
`uvicorn src.serve.app:app --reload --port 8000`.

## 8. Frontend (`src/serve/static/`)

Single page, Leaflet, OSM tiles, centred on Dubai (~25.2048, 55.2708,
zoom 11).

Layers:

1. Branch markers. Circle marker per branch. Colour = action (PROTECT
   green, HOLD amber, SHRINK red). Radius ∝ sqrt(female_pop_served),
   clamped to a sane pixel range. Permanent small label showing branch
   short name + action.
2. Community dots. Small circle per community centroid, coloured to match
   its assigned branch, opacity ∝ female population. Toggleable.
3. Assignment lines. Thin line from each community to its assigned
   branch. Toggleable, off by default (it gets busy).
4. Sibling links. When a branch is selected, draw lines to all Bedashing
   branches within 5km, labelled with the distance. This is the
   self-overlap view.

Interaction:

- Click a branch → side panel showing: all features as a labelled list,
  the decision with confidence, the rationale, key drivers highlighted,
  caveats, and a "compare to network median" column so every number has a
  reference point.
- Estimated/imputed values rendered in italics with a `~` prefix and a
  tooltip saying the value was estimated.
- Legend fixed bottom-left. Layer toggles top-right.
- A header strip showing: model backend in use, data source per dataset,
  pipeline run timestamp. The provenance must be visible on screen, not
  buried.

Keep all CSS in one small file. No dark mode, no responsive breakpoints.

## 9. What this V0 is known to get wrong

Print this list in the README and render it on the page behind an
"Assumptions" toggle. It is not a disclaimer, it is the experiment log.

1. Nearest-branch assignment is false. Real choice depends on travel
   time, malls, parking, habit, price and brand. Straight-line distance
   from a community centroid ignores all of it.
2. Community centroids are not where people live. Large communities get
   collapsed to a point.
3. No competitors. A branch with five rival salons next door looks
   identical to one with none. This is the single biggest omission.
4. Female population is a poor demand proxy. UAE population skews heavily
   male and that skew is spatially concentrated in labour accommodation
   areas, so raw density misallocates badly. Gender-split data helps but
   doesn't capture income, age, or resident-vs-tourist mix.
5. No revenue, footfall, staffing or lease data, so "SHRINK" here cannot
   distinguish a badly-located branch from a well-located, badly-run one.
6. The LLM is doing classification without ground truth and will produce
   confident-sounding labels regardless. Its agreement with the rubric is
   a sanity check, not validation.
7. Prices are a thin basket and may not be current.
8. Dubai only.

## 10. Build order and done-state

Build and verify in this order; each step must work before the next:

1. `data/seed/*.csv` populated and loading → `python -m src.acquire.run`
   prints a summary
2. Assignment + features → `python -m src.features.build` writes JSON you
   can open and eyeball
3. Rubric backend → `MODEL_BACKEND=rubric python -m src.model.run`
   produces decisions with no API key
4. Map rendering branches + decisions
5. LLM backend + caching
6. Community layer, sibling links, side panel, provenance header

`make all` runs stages 1-3. `make serve` runs the API. `make clean` wipes
`data/raw` and `data/processed` but never `data/seed`.

Done when: a fresh clone with no API key and no network runs
`make all && make serve` and shows a Dubai map with every branch coloured
by a rubric-derived action, clicking one shows its features against
network medians, and the assumptions list is visible.

## 11. First things to poke at once it runs

Not build tasks — the reason the thing exists.

- Flip `MODEL_BACKEND` and find the branches where LLM and rubric
  disagree. Read the LLM's rationale on those. Is it seeing something, or
  confabulating?
- Change `CONTEST_RATIO` from 1.25 to 1.1 and 1.5. Do the SHRINK labels
  move? If a threshold nobody justified swings the answer, the model is
  too fragile to defend.
- Delete a high-population branch from the seed and re-run. Where does
  its population go, and does any neighbour flip to PROTECT? That's your
  cannibalization story in crude form.
- Compare the map against where Bedashing actually opened. If the model
  thinks their real sites are bad, either it's wrong or you've found
  something.
