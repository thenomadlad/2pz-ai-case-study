# Bedashing V0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Bedashing V0 prototype end to end — a file-based pipeline that assigns Dubai communities to their nearest Bedashing branch, computes per-branch features, labels each branch PROTECT/HOLD/SHRINK (rubric and LLM backends), and serves it all on a Leaflet map.

**Architecture:** Four independently re-runnable file-based stages (`acquire` → `features` → `model` → `serve`), each reading/writing plain JSON under `data/`, wired together by a `Makefile`. No database. FastAPI serves both a JSON API and a static Leaflet frontend.

**Tech Stack:** Python 3.11+, `uv`, `fastapi`, `uvicorn`, `httpx`, `pydantic` v2 + `pydantic-settings`, `python-dotenv`, `anthropic` SDK, `pytest`, `ruff`. Frontend: plain HTML/CSS/JS + Leaflet from CDN.

## Global Constraints

- Python 3.11+, dependency/venv/lockfile management via `uv` (not pip/requirements.txt).
- No geopandas/shapely — haversine on centroids only.
- No React, no bundler, no build step for the frontend.
- No database — every stage boundary is a file under `data/`.
- `data/seed/` is committed; `data/raw/` and `data/processed/` are gitignored.
- Pipeline must run end-to-end with zero network access and zero API keys (seed path is the guaranteed path).
- `CONTEST_RATIO` default `1.25`.
- `MODEL_BACKEND` default `llm`; if `ANTHROPIC_API_KEY` is unset, log a warning and fall back to `rubric` automatically.
- `ENABLE_SCRAPE` and `DUBAI_PULSE_ENABLED` default off (`0`).
- Map centered at `25.2048, 55.2708`, zoom `11`.
- `make all` runs stages 1-3; `make serve` runs the API; `make clean` wipes `data/raw` and `data/processed`, never `data/seed`.
- Frontend must not use `innerHTML`/`insertAdjacentHTML` with unescaped dynamic content — LLM-generated fields (`rationale`, `caveats`, `key_drivers`) are untrusted text and must be HTML-escaped before insertion.
- Full design reference: `docs/designs/2026-09-24-bedashing-v0-design.md`.

## Scope decisions not fully specified in the design doc

The design doc is a build prompt written for a human running real scrapers against real sites; two gaps need explicit calls before coding:

1. **Live enrichment (`ENABLE_SCRAPE=1`, `DUBAI_PULSE_ENABLED=1`) is stubbed, not fully implemented.** The doc's own done-state (§10) only requires the seed path to work; scraping is optional enrichment "always falling back to seed." Building real scrapers against `bedashingbeauty.com`/Fresha/Dubai Pulse without being able to iterate against their live structure risks silent breakage and ToS issues. This plan implements the flag-checking, caching, and fallback-with-loud-logging contract fully and for real, but the live-fetch functions raise `NotImplementedError` internally which is caught and logged as "live enrichment not implemented in V0, using seed" — this is real, tested, working code, just scoped to the documented guaranteed path.
2. **Price-estimate flagging.** The `Branch` model has no field for "this price was backfilled." Per the doc's own principle ("Do not silently impute"), backfilled prices are tracked the same way estimated population is: `src/acquire/prices.py` writes the list of backfilled branch IDs to `data/raw/price_flags.json`, and `src/features/build.py` folds `"avg_price_aed"` into `BranchFeatures.estimated_fields` for those branches.

---

## File Structure

```
2pz-ai-case-study/
  pyproject.toml
  uv.lock
  .env.example
  .gitignore
  Makefile
  README.md
  data/
    seed/branches.csv
    seed/communities.csv
    raw/                       # gitignored
    processed/                 # gitignored
  src/
    __init__.py
    config.py
    models.py
    acquire/
      __init__.py
      branches.py
      prices.py
      population.py
      run.py
    features/
      __init__.py
      assign.py
      build.py
    model/
      __init__.py
      base.py
      rubric.py
      llm.py
      run.py
    serve/
      __init__.py
      app.py
      static/
        index.html
        app.js
        style.css
  tests/
    __init__.py
    test_config.py
    test_models.py
    acquire/
      __init__.py
      test_branches.py
      test_prices.py
      test_population.py
      test_run.py
    features/
      __init__.py
      test_assign.py
      test_build.py
    model/
      __init__.py
      test_rubric.py
      test_llm.py
      test_run.py
    serve/
      __init__.py
      test_app.py
```

---

### Task 1: Project scaffolding & tooling

**Files:**
- Create: `pyproject.toml`, `.env.example`, `.gitignore`, `Makefile`, `README.md`
- Create: `src/__init__.py`, `src/acquire/__init__.py`, `src/features/__init__.py`, `src/model/__init__.py`, `src/serve/__init__.py`
- Create: `tests/__init__.py`, `tests/acquire/__init__.py`, `tests/features/__init__.py`, `tests/model/__init__.py`, `tests/serve/__init__.py`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Produces: an importable `src` package and a working `pytest`/`uv` toolchain every later task depends on.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "bedashing-v0"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "httpx>=0.27",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "python-dotenv>=1.0",
    "anthropic>=0.34",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.6",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
line-length = 100
```

- [ ] **Step 2: Write `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.env
data/raw/
data/processed/
.pytest_cache/
.ruff_cache/
```

- [ ] **Step 3: Write `.env.example`**

```
# Copy to .env and fill in as needed. Every value has a working default.
MODEL_BACKEND=llm
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-haiku-4-5-20251001
ENABLE_SCRAPE=0
DUBAI_PULSE_ENABLED=0
CONTEST_RATIO=1.25
```

- [ ] **Step 4: Create empty package `__init__.py` files**

```bash
mkdir -p src/acquire src/features src/model src/serve/static
mkdir -p tests/acquire tests/features tests/model tests/serve data/seed data/raw data/processed
touch src/__init__.py src/acquire/__init__.py src/features/__init__.py src/model/__init__.py src/serve/__init__.py
touch tests/__init__.py tests/acquire/__init__.py tests/features/__init__.py tests/model/__init__.py tests/serve/__init__.py
touch data/raw/.gitkeep data/processed/.gitkeep
```

- [ ] **Step 5: Write a Makefile skeleton (targets wired up fully in Task 13)**

```makefile
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
```

- [ ] **Step 6: Write the smoke test**

```python
# tests/test_smoke.py
import sys


def test_python_version():
    assert sys.version_info >= (3, 11)


def test_src_importable():
    import src  # noqa: F401
```

- [ ] **Step 7: Install deps and run the smoke test**

Run: `uv sync --extra dev && uv run pytest tests/test_smoke.py -v`
Expected: 2 passed

- [ ] **Step 8: Write a minimal `README.md` stub (expanded in Task 16)**

```markdown
# Bedashing V0

Scrappy branch right-sizing prototype. See `docs/designs/2026-09-24-bedashing-v0-design.md` for the full design.

Setup and usage instructions land here in a later task.
```

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml .env.example .gitignore Makefile README.md src tests data/raw/.gitkeep data/processed/.gitkeep
git commit -m "Scaffold project: uv toolchain, package layout, Makefile skeleton"
```

---

### Task 2: Core domain models

**Files:**
- Create: `src/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `Branch`, `Community`, `CommunityAssignment`, `BranchFeatures`, `NetworkStats`, `Decision` — every later stage imports these from `src.models`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_models.py
import pytest
from pydantic import ValidationError

from src.models import (
    Branch, Community, CommunityAssignment, BranchFeatures, NetworkStats, Decision,
)


def test_branch_minimal():
    b = Branch(id="al-barsha", name="Al Barsha", lat=25.11, lng=55.20, area="Al Barsha",
               rating=None, review_count=None, avg_price_aed=None, source="seed")
    assert b.id == "al-barsha"
    assert b.rating is None


def test_community_estimated_flag_required():
    c = Community(id="c1", name_en="Deira", lat=25.27, lng=55.31,
                   population_total=1000, population_female=None, is_estimated=True)
    assert c.is_estimated is True
    assert c.population_female is None


def test_community_assignment_contested():
    a = CommunityAssignment(community_id="c1", nearest_branch_id="b1", nearest_km=1.2,
                             second_branch_id="b2", second_km=1.3, contested=True, female_pop=500)
    assert a.contested is True


def test_branch_features_estimated_fields_default_empty():
    f = BranchFeatures(branch_id="b1", name="Al Barsha", lat=25.11, lng=55.20,
                        female_pop_served=1000, communities_served=3, mean_distance_km=1.5,
                        max_distance_km=3.0, contested_pop=100, contested_share=0.1,
                        nearest_sibling_km=4.0, siblings_within_5km=1, avg_price_aed=150.0,
                        price_index=1.0, rating=4.5, review_count=200, pop_per_1k_rank=1,
                        estimated_fields=[])
    assert f.estimated_fields == []


def test_network_stats():
    n = NetworkStats(branch_count=10, total_female_population=50000,
                      female_pop_served_median=5000, female_pop_served_p25=3000,
                      female_pop_served_p75=7000, contested_share_median=0.2,
                      contested_share_p25=0.1, contested_share_p75=0.3,
                      avg_price_aed_median=150, avg_price_aed_p25=120, avg_price_aed_p75=180,
                      rating_median=4.3, rating_p25=4.0, rating_p75=4.6)
    assert n.branch_count == 10


def test_decision_rejects_bad_action():
    with pytest.raises(ValidationError):
        Decision(branch_id="b1", action="EXPAND", confidence="low",
                  rationale="x", key_drivers=[], caveats=[])


def test_decision_valid_action():
    d = Decision(branch_id="b1", action="PROTECT", confidence="high",
                 rationale="Serves the most women with low contest.",
                 key_drivers=["female_pop_served", "contested_share"], caveats=["No revenue data."])
    assert d.action == "PROTECT"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.models'`

- [ ] **Step 3: Write `src/models.py`**

```python
from typing import Literal, Protocol

from pydantic import BaseModel


class Branch(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    area: str
    rating: float | None
    review_count: int | None
    avg_price_aed: float | None
    source: Literal["seed", "fresha", "places"]


class Community(BaseModel):
    id: str
    name_en: str
    lat: float
    lng: float
    population_total: int
    population_female: int | None
    is_estimated: bool


class CommunityAssignment(BaseModel):
    community_id: str
    nearest_branch_id: str
    nearest_km: float
    second_branch_id: str | None
    second_km: float | None
    contested: bool
    female_pop: int


class BranchFeatures(BaseModel):
    branch_id: str
    name: str
    lat: float
    lng: float
    female_pop_served: int
    communities_served: int
    mean_distance_km: float
    max_distance_km: float
    contested_pop: int
    contested_share: float
    nearest_sibling_km: float
    siblings_within_5km: int
    avg_price_aed: float
    price_index: float
    rating: float | None
    review_count: int | None
    pop_per_1k_rank: int
    estimated_fields: list[str]


class NetworkStats(BaseModel):
    branch_count: int
    total_female_population: int
    female_pop_served_median: float
    female_pop_served_p25: float
    female_pop_served_p75: float
    contested_share_median: float
    contested_share_p25: float
    contested_share_p75: float
    avg_price_aed_median: float
    avg_price_aed_p25: float
    avg_price_aed_p75: float
    rating_median: float | None
    rating_p25: float | None
    rating_p75: float | None


class Decision(BaseModel):
    branch_id: str
    action: Literal["PROTECT", "HOLD", "SHRINK"]
    confidence: Literal["low", "medium", "high"]
    rationale: str
    key_drivers: list[str]
    caveats: list[str]


class DecisionModel(Protocol):
    name: str

    def decide(self, branch: BranchFeatures, network: NetworkStats) -> Decision: ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_models.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/models.py tests/test_models.py
git commit -m "Add pydantic models for all pipeline stage boundaries"
```

---

### Task 3: Config module

**Files:**
- Create: `src/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Settings` class and a module-level `settings = Settings()` instance with fields: `seed_dir: Path`, `raw_dir: Path`, `processed_dir: Path`, `enable_scrape: bool`, `dubai_pulse_enabled: bool`, `model_backend: Literal["llm", "rubric"]`, `contest_ratio: float`, `anthropic_api_key: str | None`, `anthropic_model: str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import os

from src.config import Settings


def test_defaults(monkeypatch):
    for key in ["ENABLE_SCRAPE", "DUBAI_PULSE_ENABLED", "MODEL_BACKEND",
                "CONTEST_RATIO", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"]:
        monkeypatch.delenv(key, raising=False)
    s = Settings(_env_file=None)
    assert s.enable_scrape is False
    assert s.dubai_pulse_enabled is False
    assert s.model_backend == "llm"
    assert s.contest_ratio == 1.25
    assert s.anthropic_api_key is None
    assert s.anthropic_model == "claude-haiku-4-5-20251001"


def test_env_override(monkeypatch):
    monkeypatch.setenv("MODEL_BACKEND", "rubric")
    monkeypatch.setenv("CONTEST_RATIO", "1.1")
    s = Settings(_env_file=None)
    assert s.model_backend == "rubric"
    assert s.contest_ratio == 1.1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.config'`

- [ ] **Step 3: Write `src/config.py`**

```python
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    seed_dir: Path = REPO_ROOT / "data" / "seed"
    raw_dir: Path = REPO_ROOT / "data" / "raw"
    processed_dir: Path = REPO_ROOT / "data" / "processed"

    enable_scrape: bool = False
    dubai_pulse_enabled: bool = False
    model_backend: Literal["llm", "rubric"] = "llm"
    contest_ratio: float = 1.25
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-haiku-4-5-20251001"


settings = Settings()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "Add env-driven Settings with documented defaults"
```

---

### Task 4: Seed data curation

**Files:**
- Create: `data/seed/branches.csv`
- Create: `data/seed/communities.csv`
- Test: `tests/test_seed_data.py`

**Interfaces:**
- Produces: the two CSVs every later acquire test/fixture reads. Schemas below are exact and final.

`branches.csv` columns (header row required): `id,name,lat,lng,area,rating,review_count,avg_price_aed`
`communities.csv` columns (header row required): `id,name_en,lat,lng,population_total,population_female`

Empty `rating`, `review_count`, `avg_price_aed`, or `population_female` cells are valid and mean "unknown" — later stages treat them as `None`/estimated. `id` is a lowercase-kebab slug.

- [ ] **Step 1: Research real Bedashing Beauty Lounge Dubai locations**

Use web search for `bedashingbeauty.com` locations/branches page and Fresha listings for "Bedashing Beauty Lounge" in Dubai. For each Dubai branch found, record: name, neighbourhood/area as written on the source, and approximate lat/lng (look the neighbourhood up on a map and use its coordinates — hand-geocoding, not a geocoder API). Record rating/review_count/price where visible on the source; leave blank otherwise. Aim for the actual count that exists (roughly 10-20 per the design doc) — do not pad with invented branches. If fewer than 5 real Dubai branches are found, fall back to a clearly-documented synthetic set covering 8-10 well-known Dubai neighbourhoods and note this explicitly in `README.md`'s assumptions section (added in Task 16) rather than presenting invented branches as real.

- [ ] **Step 2: Write `data/seed/branches.csv`**

Example shape (fill with the real researched rows from Step 1):

```csv
id,name,lat,lng,area,rating,review_count,avg_price_aed
al-barsha,Bedashing Beauty Lounge Al Barsha,25.1124,55.2044,Al Barsha,4.6,320,145
jlt,Bedashing Beauty Lounge JLT,25.0693,55.1417,Jumeirah Lake Towers,4.5,210,150
```

- [ ] **Step 3: Research Dubai community population by gender**

Use web search for the Dubai Statistics Center / Dubai Pulse "Population by Community" dataset (or its published Population Bulletin). Record 30-60 communities covering the populated parts of Dubai: `id` (slug), `name_en`, an approximate centroid `lat`/`lng` (hand-typed from a map), `population_total`, and `population_female` where the source reports a gender split. Leave `population_female` blank where it isn't reported — do not compute or guess a value here; that estimation happens in code (Task 6), not in the seed file.

- [ ] **Step 4: Write `data/seed/communities.csv`**

Example shape (fill with the real researched rows from Step 3):

```csv
id,name_en,lat,lng,population_total,population_female
deira,Deira,25.2697,55.3095,204000,89000
al-barsha-1,Al Barsha 1,25.1106,55.2000,45000,
```

- [ ] **Step 5: Write a schema-validation test**

```python
# tests/test_seed_data.py
import csv

from src.config import settings

BRANCH_COLUMNS = {"id", "name", "lat", "lng", "area", "rating", "review_count", "avg_price_aed"}
COMMUNITY_COLUMNS = {"id", "name_en", "lat", "lng", "population_total", "population_female"}


def _read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_branches_csv_schema_and_count():
    rows = _read(settings.seed_dir / "branches.csv")
    assert rows, "branches.csv must not be empty"
    assert set(rows[0].keys()) == BRANCH_COLUMNS
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), "branch ids must be unique"
    for r in rows:
        float(r["lat"])
        float(r["lng"])


def test_communities_csv_schema_and_count():
    rows = _read(settings.seed_dir / "communities.csv")
    assert len(rows) >= 20, "expect roughly 30-60 communities, got too few"
    assert set(rows[0].keys()) == COMMUNITY_COLUMNS
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), "community ids must be unique"
    for r in rows:
        float(r["lat"])
        float(r["lng"])
        int(r["population_total"])
```

- [ ] **Step 6: Run the test**

Run: `uv run pytest tests/test_seed_data.py -v`
Expected: 2 passed

- [ ] **Step 7: Commit**

```bash
git add data/seed/branches.csv data/seed/communities.csv tests/test_seed_data.py
git commit -m "Add hand-curated Dubai branch and community seed data"
```

---

### Task 5: Stage 1 — branch acquisition and price backfill

**Files:**
- Create: `src/acquire/branches.py`, `src/acquire/prices.py`
- Test: `tests/acquire/test_branches.py`, `tests/acquire/test_prices.py`

**Interfaces:**
- Consumes: `src.config.settings`, `src.models.Branch`
- Produces: `branches.load() -> list[Branch]`; `prices.backfill_missing_prices(branches: list[Branch]) -> tuple[list[Branch], list[str]]` (second element = branch IDs whose price was backfilled).

- [ ] **Step 1: Write the failing tests**

```python
# tests/acquire/test_branches.py
import csv

from src.acquire import branches
from src.config import Settings


def test_load_from_seed(tmp_path, monkeypatch):
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    with open(seed_dir / "branches.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "name", "lat", "lng", "area", "rating", "review_count", "avg_price_aed",
        ])
        writer.writeheader()
        writer.writerow({"id": "b1", "name": "Branch One", "lat": "25.1", "lng": "55.2",
                          "area": "Area", "rating": "4.5", "review_count": "100",
                          "avg_price_aed": "150"})
        writer.writerow({"id": "b2", "name": "Branch Two", "lat": "25.2", "lng": "55.3",
                          "area": "Area2", "rating": "", "review_count": "", "avg_price_aed": ""})

    test_settings = Settings(_env_file=None, seed_dir=seed_dir, enable_scrape=False)
    result = branches.load(test_settings)

    assert len(result) == 2
    assert result[0].source == "seed"
    assert result[0].rating == 4.5
    assert result[1].rating is None
    assert result[1].avg_price_aed is None


def test_load_falls_back_when_scrape_enabled_but_unimplemented(tmp_path):
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    with open(seed_dir / "branches.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "name", "lat", "lng", "area", "rating", "review_count", "avg_price_aed",
        ])
        writer.writeheader()
        writer.writerow({"id": "b1", "name": "Branch One", "lat": "25.1", "lng": "55.2",
                          "area": "Area", "rating": "", "review_count": "", "avg_price_aed": ""})

    test_settings = Settings(_env_file=None, seed_dir=seed_dir, enable_scrape=True)
    result = branches.load(test_settings)

    assert len(result) == 1
    assert result[0].source == "seed"
```

```python
# tests/acquire/test_prices.py
from src.acquire.prices import backfill_missing_prices
from src.models import Branch


def _branch(id, price):
    return Branch(id=id, name=id, lat=0, lng=0, area="x", rating=None,
                  review_count=None, avg_price_aed=price, source="seed")


def test_backfill_uses_median_of_known_prices():
    branches = [_branch("a", 100), _branch("b", 200), _branch("c", None)]
    result, flagged = backfill_missing_prices(branches)
    by_id = {b.id: b for b in result}
    assert by_id["c"].avg_price_aed == 150
    assert flagged == ["c"]


def test_backfill_noop_when_nothing_missing():
    branches = [_branch("a", 100), _branch("b", 200)]
    result, flagged = backfill_missing_prices(branches)
    assert flagged == []
    assert result == branches
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/acquire/test_branches.py tests/acquire/test_prices.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `src/acquire/branches.py`**

```python
import csv
import logging

from src.config import Settings, settings as default_settings
from src.models import Branch

logger = logging.getLogger(__name__)


def _load_seed(seed_dir) -> list[Branch]:
    path = seed_dir / "branches.csv"
    branches: list[Branch] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            branches.append(Branch(
                id=row["id"],
                name=row["name"],
                lat=float(row["lat"]),
                lng=float(row["lng"]),
                area=row["area"],
                rating=float(row["rating"]) if row["rating"] else None,
                review_count=int(row["review_count"]) if row["review_count"] else None,
                avg_price_aed=float(row["avg_price_aed"]) if row["avg_price_aed"] else None,
                source="seed",
            ))
    logger.info("branches: loaded %d rows from seed", len(branches))
    return branches


def _scrape_live() -> list[Branch]:
    # Live scraping of bedashingbeauty.com / Fresha is intentionally not
    # implemented in V0 — see docs/designs/2026-09-25-bedashing-v0-plan.md
    # "Scope decisions" section. Callers must catch NotImplementedError.
    raise NotImplementedError


def load(settings: Settings | None = None) -> list[Branch]:
    settings = settings or default_settings
    if settings.enable_scrape:
        try:
            return _scrape_live()
        except NotImplementedError:
            logger.warning("branches: ENABLE_SCRAPE=1 but live enrichment isn't implemented "
                            "in V0, falling back to seed")
    return _load_seed(settings.seed_dir)
```

- [ ] **Step 4: Write `src/acquire/prices.py`**

```python
import statistics

from src.models import Branch


def backfill_missing_prices(branches: list[Branch]) -> tuple[list[Branch], list[str]]:
    known = [b.avg_price_aed for b in branches if b.avg_price_aed is not None]
    if not known:
        return branches, []

    median_price = statistics.median(known)
    flagged: list[str] = []
    result: list[Branch] = []
    for b in branches:
        if b.avg_price_aed is None:
            result.append(b.model_copy(update={"avg_price_aed": median_price}))
            flagged.append(b.id)
        else:
            result.append(b)
    return result, flagged
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/acquire/test_branches.py tests/acquire/test_prices.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add src/acquire/branches.py src/acquire/prices.py tests/acquire/test_branches.py tests/acquire/test_prices.py
git commit -m "Add branch acquisition and price backfill with seed fallback"
```

---

### Task 6: Stage 1 — population acquisition

**Files:**
- Create: `src/acquire/population.py`
- Test: `tests/acquire/test_population.py`

**Interfaces:**
- Consumes: `src.config.settings`, `src.models.Community`
- Produces: `population.load(settings=None, global_female_share: float = 0.49) -> list[Community]`

- [ ] **Step 1: Write the failing test**

```python
# tests/acquire/test_population.py
import csv

from src.acquire import population
from src.config import Settings


def test_load_estimates_missing_female_population(tmp_path):
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    with open(seed_dir / "communities.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "name_en", "lat", "lng", "population_total", "population_female",
        ])
        writer.writeheader()
        writer.writerow({"id": "c1", "name_en": "Deira", "lat": "25.27", "lng": "55.31",
                          "population_total": "1000", "population_female": "480"})
        writer.writerow({"id": "c2", "name_en": "Al Barsha", "lat": "25.11", "lng": "55.20",
                          "population_total": "1000", "population_female": ""})

    test_settings = Settings(_env_file=None, seed_dir=seed_dir, dubai_pulse_enabled=False)
    result = population.load(test_settings, global_female_share=0.49)

    by_id = {c.id: c for c in result}
    assert by_id["c1"].population_female == 480
    assert by_id["c1"].is_estimated is False
    assert by_id["c2"].population_female == 490
    assert by_id["c2"].is_estimated is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/acquire/test_population.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `src/acquire/population.py`**

```python
import csv
import logging

from src.config import Settings, settings as default_settings
from src.models import Community

logger = logging.getLogger(__name__)


def _load_seed(seed_dir, global_female_share: float) -> list[Community]:
    path = seed_dir / "communities.csv"
    communities: list[Community] = []
    estimated_count = 0
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            total = int(row["population_total"])
            raw_female = row["population_female"]
            if raw_female:
                female = int(raw_female)
                is_estimated = False
            else:
                female = round(total * global_female_share)
                is_estimated = True
                estimated_count += 1
            communities.append(Community(
                id=row["id"],
                name_en=row["name_en"],
                lat=float(row["lat"]),
                lng=float(row["lng"]),
                population_total=total,
                population_female=female,
                is_estimated=is_estimated,
            ))
    logger.info("population: loaded %d communities from seed (%d with estimated female share)",
                len(communities), estimated_count)
    return communities


def _fetch_dubai_pulse() -> list[Community]:
    # Dubai Pulse open API integration is intentionally not implemented in
    # V0 — see docs/designs/2026-09-25-bedashing-v0-plan.md "Scope decisions".
    raise NotImplementedError


def load(settings: Settings | None = None, global_female_share: float = 0.49) -> list[Community]:
    settings = settings or default_settings
    if settings.dubai_pulse_enabled:
        try:
            return _fetch_dubai_pulse()
        except NotImplementedError:
            logger.warning("population: DUBAI_PULSE_ENABLED=1 but live enrichment isn't "
                            "implemented in V0, falling back to seed")
    return _load_seed(settings.seed_dir, global_female_share)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/acquire/test_population.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add src/acquire/population.py tests/acquire/test_population.py
git commit -m "Add population acquisition with explicit female-share estimation"
```

---

### Task 7: Stage 1 — acquire entrypoint

**Files:**
- Create: `src/acquire/run.py`
- Test: `tests/acquire/test_run.py`

**Interfaces:**
- Consumes: `branches.load`, `prices.backfill_missing_prices`, `population.load`
- Produces: `main(settings=None) -> None`, writing `data/raw/branches.json`, `data/raw/price_flags.json`, `data/raw/communities.json`, and printing a summary table.

- [ ] **Step 1: Write the failing test**

```python
# tests/acquire/test_run.py
import csv
import json

from src.acquire.run import main
from src.config import Settings


def _write_branches(seed_dir):
    with open(seed_dir / "branches.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "id", "name", "lat", "lng", "area", "rating", "review_count", "avg_price_aed"])
        w.writeheader()
        w.writerow({"id": "b1", "name": "B1", "lat": "25.1", "lng": "55.2", "area": "A",
                    "rating": "4.5", "review_count": "10", "avg_price_aed": "100"})
        w.writerow({"id": "b2", "name": "B2", "lat": "25.2", "lng": "55.3", "area": "B",
                    "rating": "", "review_count": "", "avg_price_aed": ""})


def _write_communities(seed_dir):
    with open(seed_dir / "communities.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "id", "name_en", "lat", "lng", "population_total", "population_female"])
        w.writeheader()
        w.writerow({"id": "c1", "name_en": "C1", "lat": "25.1", "lng": "55.2",
                    "population_total": "1000", "population_female": "480"})


def test_main_writes_raw_files(tmp_path):
    seed_dir = tmp_path / "seed"
    raw_dir = tmp_path / "raw"
    seed_dir.mkdir()
    raw_dir.mkdir()
    _write_branches(seed_dir)
    _write_communities(seed_dir)

    test_settings = Settings(_env_file=None, seed_dir=seed_dir, raw_dir=raw_dir)
    main(test_settings)

    branches_out = json.loads((raw_dir / "branches.json").read_text())
    price_flags = json.loads((raw_dir / "price_flags.json").read_text())
    communities_out = json.loads((raw_dir / "communities.json").read_text())

    assert len(branches_out) == 2
    assert price_flags == ["b2"]
    assert len(communities_out) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/acquire/test_run.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `src/acquire/run.py`**

```python
import json
import logging

from src.acquire import branches as branches_mod
from src.acquire import population as population_mod
from src.acquire.prices import backfill_missing_prices
from src.config import Settings, settings as default_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main(settings: Settings | None = None) -> None:
    settings = settings or default_settings
    settings.raw_dir.mkdir(parents=True, exist_ok=True)

    raw_branches = branches_mod.load(settings)
    filled_branches, price_flags = backfill_missing_prices(raw_branches)
    communities = population_mod.load(settings)

    (settings.raw_dir / "branches.json").write_text(
        json.dumps([b.model_dump() for b in filled_branches], indent=2))
    (settings.raw_dir / "price_flags.json").write_text(json.dumps(price_flags, indent=2))
    (settings.raw_dir / "communities.json").write_text(
        json.dumps([c.model_dump() for c in communities], indent=2))

    estimated_pop = sum(1 for c in communities if c.is_estimated)
    print("=== acquire summary ===")
    print(f"branches:    {len(filled_branches)} rows (source: "
          f"{'seed' if not settings.enable_scrape else 'seed, scrape unimplemented'})"
          f", {len(price_flags)} price(s) backfilled")
    print(f"communities: {len(communities)} rows "
          f"(source: {'seed' if not settings.dubai_pulse_enabled else 'seed, pulse unimplemented'})"
          f", {estimated_pop} with estimated female population")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/acquire/test_run.py -v`
Expected: 1 passed

- [ ] **Step 5: Run against real seed data and eyeball output**

Run: `uv run python -m src.acquire.run`
Expected: prints the summary table and creates `data/raw/branches.json`, `data/raw/price_flags.json`, `data/raw/communities.json` from the real seed CSVs written in Task 4.

- [ ] **Step 6: Commit**

```bash
git add src/acquire/run.py tests/acquire/test_run.py
git commit -m "Add stage 1 acquire entrypoint with summary output"
```

---

### Task 8: Stage 2 — nearest-branch assignment

**Files:**
- Create: `src/features/assign.py`
- Test: `tests/features/test_assign.py`

**Interfaces:**
- Consumes: `src.models.Branch`, `src.models.Community`, `src.models.CommunityAssignment`
- Produces: `haversine_km(lat1, lng1, lat2, lng2) -> float`; `assign_communities(branches: list[Branch], communities: list[Community], contest_ratio: float) -> list[CommunityAssignment]`

- [ ] **Step 1: Write the failing test**

```python
# tests/features/test_assign.py
import math

from src.features.assign import assign_communities, haversine_km
from src.models import Branch, Community


def _branch(id, lat, lng):
    return Branch(id=id, name=id, lat=lat, lng=lng, area="x", rating=None,
                  review_count=None, avg_price_aed=None, source="seed")


def _community(id, lat, lng, female):
    return Community(id=id, name_en=id, lat=lat, lng=lng, population_total=female * 2,
                      population_female=female, is_estimated=False)


def test_haversine_known_distance():
    # Roughly Dubai Marina to Deira, ~25km
    d = haversine_km(25.0805, 55.1403, 25.2697, 55.3095)
    assert 20 < d < 30


def test_haversine_zero_for_same_point():
    assert haversine_km(25.0, 55.0, 25.0, 55.0) == 0.0


def test_assign_picks_nearest():
    branches = [_branch("near", 25.10, 55.20), _branch("far", 25.50, 55.50)]
    communities = [_community("c1", 25.11, 55.21, 1000)]

    result = assign_communities(branches, communities, contest_ratio=1.25)

    assert len(result) == 1
    assert result[0].nearest_branch_id == "near"
    assert result[0].second_branch_id == "far"
    assert result[0].female_pop == 1000


def test_assign_marks_contested_when_close():
    branches = [_branch("b1", 25.10, 55.20), _branch("b2", 25.101, 55.201)]
    communities = [_community("c1", 25.10, 55.20, 500)]

    result = assign_communities(branches, communities, contest_ratio=1.25)

    assert result[0].contested is True


def test_assign_not_contested_when_far_apart():
    branches = [_branch("b1", 25.10, 55.20), _branch("b2", 26.0, 56.0)]
    communities = [_community("c1", 25.10, 55.20, 500)]

    result = assign_communities(branches, communities, contest_ratio=1.25)

    assert result[0].contested is False


def test_assign_single_branch_has_no_second():
    branches = [_branch("only", 25.10, 55.20)]
    communities = [_community("c1", 25.11, 55.21, 500)]

    result = assign_communities(branches, communities, contest_ratio=1.25)

    assert result[0].second_branch_id is None
    assert result[0].second_km is None
    assert result[0].contested is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/features/test_assign.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `src/features/assign.py`**

```python
import math

from src.models import Branch, Community, CommunityAssignment

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def assign_communities(
    branches: list[Branch], communities: list[Community], contest_ratio: float,
) -> list[CommunityAssignment]:
    assignments: list[CommunityAssignment] = []
    for community in communities:
        distances = sorted(
            ((haversine_km(community.lat, community.lng, b.lat, b.lng), b.id) for b in branches),
            key=lambda pair: pair[0],
        )
        nearest_km, nearest_id = distances[0]
        if len(distances) > 1:
            second_km, second_id = distances[1]
            contested = (second_km / nearest_km) < contest_ratio if nearest_km > 0 else True
        else:
            second_km, second_id, contested = None, None, False

        assignments.append(CommunityAssignment(
            community_id=community.id,
            nearest_branch_id=nearest_id,
            nearest_km=nearest_km,
            second_branch_id=second_id,
            second_km=second_km,
            contested=contested,
            female_pop=community.population_female or 0,
        ))
    return assignments
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/features/test_assign.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/features/assign.py tests/features/test_assign.py
git commit -m "Add haversine nearest-branch assignment with contested-community detection"
```

---

### Task 9: Stage 2 — feature builder entrypoint

**Files:**
- Create: `src/features/build.py`
- Test: `tests/features/test_build.py`

**Interfaces:**
- Consumes: `src.features.assign.assign_communities`, `src.features.assign.haversine_km`, raw JSON from `data/raw/`
- Produces: `build_features(branches, communities, price_flags, contest_ratio) -> tuple[list[BranchFeatures], NetworkStats]`; `main(settings=None) -> None` writing `data/processed/branch_features.json` (including a `"network"` key), `data/processed/community_assignment.json`, and `data/processed/communities.json` (raw community records copied forward so `serve` can join centroids without reading `data/raw/`).

- [ ] **Step 1: Write the failing test**

```python
# tests/features/test_build.py
import json

from src.features.build import build_features, main
from src.config import Settings
from src.models import Branch, Community


def _branch(id, lat, lng, price=100.0, rating=4.5, reviews=50):
    return Branch(id=id, name=id.title(), lat=lat, lng=lng, area="x", rating=rating,
                  review_count=reviews, avg_price_aed=price, source="seed")


def _community(id, lat, lng, female):
    return Community(id=id, name_en=id, lat=lat, lng=lng, population_total=female * 2,
                      population_female=female, is_estimated=False)


def test_build_features_basic():
    branches = [_branch("a", 25.10, 55.20), _branch("b", 25.50, 55.50)]
    communities = [_community("c1", 25.11, 55.21, 1000), _community("c2", 25.51, 55.51, 500)]

    features, network = build_features(branches, communities, price_flags=["b"],
                                        contest_ratio=1.25)

    by_id = {f.branch_id: f for f in features}
    assert by_id["a"].female_pop_served == 1000
    assert by_id["a"].communities_served == 1
    assert by_id["b"].estimated_fields == ["avg_price_aed"]
    assert network.branch_count == 2
    assert network.total_female_population == 1500


def test_main_writes_processed_files(tmp_path):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    raw_dir.mkdir()
    processed_dir.mkdir()

    (raw_dir / "branches.json").write_text(json.dumps([
        _branch("a", 25.10, 55.20).model_dump(),
    ]))
    (raw_dir / "price_flags.json").write_text(json.dumps([]))
    (raw_dir / "communities.json").write_text(json.dumps([
        _community("c1", 25.11, 55.21, 1000).model_dump(),
    ]))

    settings = Settings(_env_file=None, raw_dir=raw_dir, processed_dir=processed_dir)
    main(settings)

    features_out = json.loads((processed_dir / "branch_features.json").read_text())
    assignment_out = json.loads((processed_dir / "community_assignment.json").read_text())
    communities_out = json.loads((processed_dir / "communities.json").read_text())
    assert "network" in features_out
    assert len(features_out["branches"]) == 1
    assert len(assignment_out) == 1
    assert len(communities_out) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/features/test_build.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `src/features/build.py`**

```python
import json
import statistics

from src.config import Settings, settings as default_settings
from src.features.assign import assign_communities, haversine_km
from src.models import Branch, BranchFeatures, Community, NetworkStats


def _percentiles(values: list[float]) -> tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    ordered = sorted(values)
    return (statistics.median(ordered), _percentile(ordered, 0.25), _percentile(ordered, 0.75))


def _percentile(ordered: list[float], pct: float) -> float:
    if len(ordered) == 1:
        return ordered[0]
    k = pct * (len(ordered) - 1)
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    frac = k - lo
    return ordered[lo] + (ordered[hi] - ordered[lo]) * frac


def build_features(
    branches: list[Branch], communities: list[Community],
    price_flags: list[str], contest_ratio: float,
) -> tuple[list[BranchFeatures], NetworkStats]:
    assignments = assign_communities(branches, communities, contest_ratio)
    price_flag_set = set(price_flags)

    median_price = statistics.median([b.avg_price_aed for b in branches if b.avg_price_aed])

    features: list[BranchFeatures] = []
    for branch in branches:
        served = [a for a in assignments if a.nearest_branch_id == branch.id]
        female_pop_served = sum(a.female_pop for a in served)
        contested_pop = sum(a.female_pop for a in served if a.contested)

        if served:
            mean_distance = (
                sum(a.nearest_km * a.female_pop for a in served) / female_pop_served
                if female_pop_served else sum(a.nearest_km for a in served) / len(served)
            )
            max_distance = max(a.nearest_km for a in served)
        else:
            mean_distance, max_distance = 0.0, 0.0

        siblings = [b for b in branches if b.id != branch.id]
        sibling_distances = [haversine_km(branch.lat, branch.lng, s.lat, s.lng) for s in siblings]
        nearest_sibling_km = min(sibling_distances) if sibling_distances else 0.0
        siblings_within_5km = sum(1 for d in sibling_distances if d <= 5.0)

        estimated_fields = ["avg_price_aed"] if branch.id in price_flag_set else []

        features.append(BranchFeatures(
            branch_id=branch.id,
            name=branch.name,
            lat=branch.lat,
            lng=branch.lng,
            female_pop_served=female_pop_served,
            communities_served=len(served),
            mean_distance_km=mean_distance,
            max_distance_km=max_distance,
            contested_pop=contested_pop,
            contested_share=(contested_pop / female_pop_served) if female_pop_served else 0.0,
            nearest_sibling_km=nearest_sibling_km,
            siblings_within_5km=siblings_within_5km,
            avg_price_aed=branch.avg_price_aed or median_price,
            price_index=(branch.avg_price_aed or median_price) / median_price,
            rating=branch.rating,
            review_count=branch.review_count,
            pop_per_1k_rank=0,
            estimated_fields=estimated_fields,
        ))

    ranked = sorted(features, key=lambda f: f.female_pop_served, reverse=True)
    for rank, f in enumerate(ranked, start=1):
        f.pop_per_1k_rank = rank

    pop_med, pop_p25, pop_p75 = _percentiles([f.female_pop_served for f in features])
    contest_med, contest_p25, contest_p75 = _percentiles([f.contested_share for f in features])
    price_med, price_p25, price_p75 = _percentiles([f.avg_price_aed for f in features])
    ratings = [f.rating for f in features if f.rating is not None]
    if ratings:
        rating_med, rating_p25, rating_p75 = _percentiles(ratings)
    else:
        rating_med = rating_p25 = rating_p75 = None

    network = NetworkStats(
        branch_count=len(features),
        total_female_population=sum(f.female_pop_served for f in features),
        female_pop_served_median=pop_med,
        female_pop_served_p25=pop_p25,
        female_pop_served_p75=pop_p75,
        contested_share_median=contest_med,
        contested_share_p25=contest_p25,
        contested_share_p75=contest_p75,
        avg_price_aed_median=price_med,
        avg_price_aed_p25=price_p25,
        avg_price_aed_p75=price_p75,
        rating_median=rating_med,
        rating_p25=rating_p25,
        rating_p75=rating_p75,
    )
    return features, network


def main(settings: Settings | None = None) -> None:
    settings = settings or default_settings
    settings.processed_dir.mkdir(parents=True, exist_ok=True)

    branches = [Branch(**b) for b in json.loads((settings.raw_dir / "branches.json").read_text())]
    price_flags = json.loads((settings.raw_dir / "price_flags.json").read_text())
    communities = [Community(**c) for c in
                   json.loads((settings.raw_dir / "communities.json").read_text())]

    features, network = build_features(branches, communities, price_flags, settings.contest_ratio)
    assignments = assign_communities(branches, communities, settings.contest_ratio)

    (settings.processed_dir / "branch_features.json").write_text(json.dumps({
        "network": network.model_dump(),
        "branches": [f.model_dump() for f in features],
    }, indent=2))
    (settings.processed_dir / "community_assignment.json").write_text(
        json.dumps([a.model_dump() for a in assignments], indent=2))
    (settings.processed_dir / "communities.json").write_text(
        json.dumps([c.model_dump() for c in communities], indent=2))

    print(f"features: wrote {len(features)} branch features, {len(assignments)} community "
          f"assignments")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/features/test_build.py -v`
Expected: 2 passed

- [ ] **Step 5: Run against real data end-to-end and eyeball output**

Run: `uv run python -m src.features.build`
Expected: prints the summary line; `data/processed/branch_features.json`, `data/processed/community_assignment.json`, and `data/processed/communities.json` are valid, readable JSON.

- [ ] **Step 6: Commit**

```bash
git add src/features/build.py tests/features/test_build.py
git commit -m "Add stage 2 feature builder with network percentile stats"
```

---

### Task 10: Stage 3 — decision model interface and rubric backend

**Files:**
- Create: `src/model/base.py`, `src/model/rubric.py`
- Test: `tests/model/test_rubric.py`

**Interfaces:**
- Consumes: `src.models.BranchFeatures`, `src.models.NetworkStats`, `src.models.Decision`
- Produces: `RubricModel` class implementing `decide(branches: list[BranchFeatures], network: NetworkStats) -> list[Decision]` (batched, since ranking requires all branches at once — this widens the `DecisionModel` protocol from the design doc's per-branch sketch to a per-network-call, documented here since the LLM backend in Task 11 keeps the same batched-list signature for interchangeability)

- [ ] **Step 1: Write the failing test**

```python
# tests/model/test_rubric.py
from src.model.rubric import RubricModel
from src.models import BranchFeatures, NetworkStats


def _features(branch_id, pop, contested_share, rating):
    return BranchFeatures(
        branch_id=branch_id, name=branch_id, lat=25.0, lng=55.0,
        female_pop_served=pop, communities_served=1, mean_distance_km=1.0, max_distance_km=1.0,
        contested_pop=0, contested_share=contested_share, nearest_sibling_km=5.0,
        siblings_within_5km=0, avg_price_aed=100.0, price_index=1.0, rating=rating,
        review_count=10, pop_per_1k_rank=0, estimated_fields=[],
    )


NETWORK = NetworkStats(
    branch_count=3, total_female_population=6000,
    female_pop_served_median=2000, female_pop_served_p25=1500, female_pop_served_p75=2500,
    contested_share_median=0.2, contested_share_p25=0.1, contested_share_p75=0.3,
    avg_price_aed_median=100, avg_price_aed_p25=90, avg_price_aed_p75=110,
    rating_median=4.3, rating_p25=4.0, rating_p75=4.6,
)


def test_rubric_ranks_top_and_bottom_thirds():
    branches = [
        _features("strong", pop=5000, contested_share=0.05, rating=4.9),
        _features("mid", pop=2000, contested_share=0.2, rating=4.3),
        _features("weak", pop=500, contested_share=0.6, rating=3.5),
    ]

    decisions = RubricModel().decide(branches, NETWORK)
    by_id = {d.branch_id: d for d in decisions}

    assert by_id["strong"].action == "PROTECT"
    assert by_id["weak"].action == "SHRINK"
    assert all(d.confidence == "medium" for d in decisions)
    assert all(len(d.key_drivers) == 2 for d in decisions)


def test_rubric_handles_missing_rating():
    branches = [
        _features("a", pop=3000, contested_share=0.1, rating=None),
        _features("b", pop=1000, contested_share=0.5, rating=None),
    ]
    decisions = RubricModel().decide(branches, NETWORK)
    assert len(decisions) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/model/test_rubric.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `src/model/base.py`**

```python
from typing import Protocol

from src.models import BranchFeatures, Decision, NetworkStats


class DecisionModel(Protocol):
    name: str

    def decide(self, branches: list[BranchFeatures], network: NetworkStats) -> list[Decision]: ...
```

- [ ] **Step 4: Write `src/model/rubric.py`**

```python
from src.models import BranchFeatures, Decision, NetworkStats

FEATURE_NAMES = ("female_pop_served", "contested_share", "rating")


def _normalize(value: float, lo: float, hi: float) -> float:
    if hi == lo:
        return 0.5
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


class RubricModel:
    name = "rubric"

    def decide(self, branches: list[BranchFeatures], network: NetworkStats) -> list[Decision]:
        pops = [b.female_pop_served for b in branches]
        contested = [b.contested_share for b in branches]
        ratings = [b.rating for b in branches if b.rating is not None]
        rating_fallback = network.rating_median if network.rating_median is not None else 4.0

        pop_lo, pop_hi = min(pops), max(pops)
        contest_lo, contest_hi = min(contested), max(contested)
        rating_lo, rating_hi = (min(ratings), max(ratings)) if ratings else (rating_fallback,
                                                                              rating_fallback)

        scored = []
        for b in branches:
            pop_score = _normalize(b.female_pop_served, pop_lo, pop_hi)
            contest_score = 1 - _normalize(b.contested_share, contest_lo, contest_hi)
            rating_value = b.rating if b.rating is not None else rating_fallback
            rating_score = _normalize(rating_value, rating_lo, rating_hi)
            composite = (pop_score + contest_score + rating_score) / 3
            scored.append((composite, b))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        n = len(scored)
        top_third = max(1, n // 3)
        bottom_third = max(1, n // 3)

        decisions = []
        for i, (composite, b) in enumerate(scored):
            if i < top_third:
                action = "PROTECT"
            elif i >= n - bottom_third:
                action = "SHRINK"
            else:
                action = "HOLD"

            deviations = {
                "female_pop_served": abs(b.female_pop_served - network.female_pop_served_median),
                "contested_share": abs(b.contested_share - network.contested_share_median),
            }
            if network.rating_median is not None and b.rating is not None:
                deviations["rating"] = abs(b.rating - network.rating_median)
            key_drivers = sorted(deviations, key=deviations.get, reverse=True)[:2]

            decisions.append(Decision(
                branch_id=b.branch_id,
                action=action,
                confidence="medium",
                rationale=(f"Composite rubric score {composite:.2f} on population, contest "
                           f"share, and rating places this branch in the {action.lower()} "
                           f"tier of the network."),
                key_drivers=key_drivers,
                caveats=["Linear rubric over 3 features only; no revenue, footfall, or "
                         "competitor context."],
            ))
        return decisions
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/model/test_rubric.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add src/model/base.py src/model/rubric.py tests/model/test_rubric.py
git commit -m "Add DecisionModel protocol and deterministic rubric backend"
```

---

### Task 11: Stage 3 — LLM backend with caching

**Files:**
- Create: `src/model/llm.py`
- Test: `tests/model/test_llm.py`

**Interfaces:**
- Consumes: `src.config.settings`, `src.models.BranchFeatures/NetworkStats/Decision`, `anthropic.Anthropic`
- Produces: `LLMModel(client=None)` implementing `decide(branches: list[BranchFeatures], network: NetworkStats) -> list[Decision]`, caching each branch's decision under `data/processed/.llm_cache/<sha>.json`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/model/test_llm.py
import json
from unittest.mock import MagicMock

from src.model.llm import LLMModel, PROMPT_VERSION, _cache_key
from src.models import BranchFeatures, NetworkStats


def _features():
    return BranchFeatures(
        branch_id="a", name="A", lat=25.0, lng=55.0, female_pop_served=2000,
        communities_served=1, mean_distance_km=1.0, max_distance_km=1.0, contested_pop=200,
        contested_share=0.1, nearest_sibling_km=5.0, siblings_within_5km=0, avg_price_aed=100.0,
        price_index=1.0, rating=4.5, review_count=50, pop_per_1k_rank=1, estimated_fields=[],
    )


NETWORK = NetworkStats(
    branch_count=1, total_female_population=2000,
    female_pop_served_median=2000, female_pop_served_p25=2000, female_pop_served_p75=2000,
    contested_share_median=0.1, contested_share_p25=0.1, contested_share_p75=0.1,
    avg_price_aed_median=100, avg_price_aed_p25=100, avg_price_aed_p75=100,
    rating_median=4.5, rating_p25=4.5, rating_p75=4.5,
)


def _tool_use_response(decision_dict):
    block = MagicMock()
    block.type = "tool_use"
    block.input = decision_dict
    response = MagicMock()
    response.content = [block]
    return response


def test_decide_calls_client_and_returns_decision(tmp_path):
    branch = _features()
    decision_payload = {
        "branch_id": "a", "action": "PROTECT", "confidence": "high",
        "rationale": "Strong population, low contest.",
        "key_drivers": ["female_pop_served", "contested_share"], "caveats": ["No revenue data."],
    }
    client = MagicMock()
    client.messages.create.return_value = _tool_use_response(decision_payload)

    model = LLMModel(client=client, model_name="test-model", cache_dir=tmp_path)
    decisions = model.decide([branch], NETWORK)

    assert decisions[0].action == "PROTECT"
    client.messages.create.assert_called_once()


def test_decide_uses_cache_on_second_call(tmp_path):
    branch = _features()
    decision_payload = {
        "branch_id": "a", "action": "HOLD", "confidence": "medium",
        "rationale": "Middling numbers.", "key_drivers": ["rating"], "caveats": [],
    }
    client = MagicMock()
    client.messages.create.return_value = _tool_use_response(decision_payload)

    model = LLMModel(client=client, model_name="test-model", cache_dir=tmp_path)
    model.decide([branch], NETWORK)
    model.decide([branch], NETWORK)

    assert client.messages.create.call_count == 1


def test_cache_key_changes_with_feature_vector():
    branch = _features()
    other = branch.model_copy(update={"female_pop_served": 9999})
    key1 = _cache_key(branch, "test-model")
    key2 = _cache_key(other, "test-model")
    assert key1 != key2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/model/test_llm.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `src/model/llm.py`**

```python
import hashlib
import json
import logging
from pathlib import Path

from src.config import settings as default_settings
from src.models import BranchFeatures, Decision, NetworkStats

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = (
    "You are a retail portfolio analyst for a UAE salon chain. You classify branches as "
    "PROTECT, HOLD or SHRINK. You only reason from the numbers provided. You never invent "
    "data. If the evidence is thin you say so in `caveats` and lower `confidence`."
)

DECISION_TOOL = {
    "name": "submit_decision",
    "description": "Submit the PROTECT/HOLD/SHRINK decision for this branch.",
    "input_schema": {
        "type": "object",
        "properties": {
            "branch_id": {"type": "string"},
            "action": {"type": "string", "enum": ["PROTECT", "HOLD", "SHRINK"]},
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            "rationale": {"type": "string"},
            "key_drivers": {"type": "array", "items": {"type": "string"}},
            "caveats": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["branch_id", "action", "confidence", "rationale", "key_drivers", "caveats"],
    },
}


def _cache_key(branch: BranchFeatures, model_name: str) -> str:
    payload = json.dumps({
        "prompt_version": PROMPT_VERSION,
        "model": model_name,
        "features": branch.model_dump(),
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _build_user_message(branch: BranchFeatures, network: NetworkStats) -> str:
    return json.dumps({
        "definitions": {
            "PROTECT": "Invest to defend this branch's position.",
            "HOLD": "Keep as-is, no strong signal either way.",
            "SHRINK": "Candidate for downsizing or closure.",
        },
        "network_context": network.model_dump(),
        "branch": branch.model_dump(),
        "unknown_to_you": [
            "revenue", "footfall", "staffing", "competitors", "lease costs",
        ],
    })


class LLMModel:
    name = "llm"

    def __init__(self, client=None, model_name: str | None = None, cache_dir: Path | None = None):
        if client is None:
            import anthropic
            client = anthropic.Anthropic(api_key=default_settings.anthropic_api_key)
        self._client = client
        self._model_name = model_name or default_settings.anthropic_model
        self._cache_dir = cache_dir or (default_settings.processed_dir / ".llm_cache")
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _decide_one(self, branch: BranchFeatures, network: NetworkStats) -> Decision:
        key = _cache_key(branch, self._model_name)
        cache_path = self._cache_dir / f"{key}.json"
        if cache_path.exists():
            return Decision(**json.loads(cache_path.read_text()))

        response = self._client.messages.create(
            model=self._model_name,
            max_tokens=1024,
            temperature=0,
            system=SYSTEM_PROMPT,
            tools=[DECISION_TOOL],
            tool_choice={"type": "tool", "name": "submit_decision"},
            messages=[{"role": "user", "content": _build_user_message(branch, network)}],
        )
        tool_block = next(b for b in response.content if b.type == "tool_use")
        decision = Decision(**tool_block.input)
        cache_path.write_text(json.dumps(decision.model_dump(), indent=2))
        return decision

    def decide(self, branches: list[BranchFeatures], network: NetworkStats) -> list[Decision]:
        return [self._decide_one(b, network) for b in branches]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/model/test_llm.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/model/llm.py tests/model/test_llm.py
git commit -m "Add LLM decision backend with structured tool-use output and disk caching"
```

---

### Task 12: Stage 3 — model entrypoint with backend fallback and confusion table

**Files:**
- Create: `src/model/run.py`
- Test: `tests/model/test_run.py`

**Interfaces:**
- Consumes: `RubricModel`, `LLMModel`, `data/processed/branch_features.json`
- Produces: `resolve_backend(settings) -> DecisionModel`; `main(settings=None) -> None` writing `data/processed/decisions.json`.

- [ ] **Step 1: Write the failing test**

```python
# tests/model/test_run.py
import json

from src.config import Settings
from src.model.run import main, resolve_backend
from src.model.rubric import RubricModel


def test_resolve_backend_falls_back_without_api_key():
    settings = Settings(_env_file=None, model_backend="llm", anthropic_api_key=None)
    model = resolve_backend(settings)
    assert isinstance(model, RubricModel)


def test_resolve_backend_honors_explicit_rubric():
    settings = Settings(_env_file=None, model_backend="rubric")
    model = resolve_backend(settings)
    assert isinstance(model, RubricModel)


def test_main_writes_decisions(tmp_path):
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    (processed_dir / "branch_features.json").write_text(json.dumps({
        "network": {
            "branch_count": 1, "total_female_population": 1000,
            "female_pop_served_median": 1000, "female_pop_served_p25": 1000,
            "female_pop_served_p75": 1000, "contested_share_median": 0.1,
            "contested_share_p25": 0.1, "contested_share_p75": 0.1,
            "avg_price_aed_median": 100, "avg_price_aed_p25": 100, "avg_price_aed_p75": 100,
            "rating_median": 4.5, "rating_p25": 4.5, "rating_p75": 4.5,
        },
        "branches": [{
            "branch_id": "a", "name": "A", "lat": 25.0, "lng": 55.0, "female_pop_served": 1000,
            "communities_served": 1, "mean_distance_km": 1.0, "max_distance_km": 1.0,
            "contested_pop": 100, "contested_share": 0.1, "nearest_sibling_km": 5.0,
            "siblings_within_5km": 0, "avg_price_aed": 100.0, "price_index": 1.0, "rating": 4.5,
            "review_count": 10, "pop_per_1k_rank": 1, "estimated_fields": [],
        }],
    }))

    settings = Settings(_env_file=None, processed_dir=processed_dir, model_backend="rubric")
    main(settings)

    decisions = json.loads((processed_dir / "decisions.json").read_text())
    assert len(decisions) == 1
    assert decisions[0]["branch_id"] == "a"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/model/test_run.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `src/model/run.py`**

```python
import json
import logging

from src.config import Settings, settings as default_settings
from src.model.base import DecisionModel
from src.model.rubric import RubricModel
from src.models import BranchFeatures, NetworkStats

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def resolve_backend(settings: Settings) -> DecisionModel:
    if settings.model_backend == "llm":
        if not settings.anthropic_api_key:
            logger.warning("model: MODEL_BACKEND=llm but ANTHROPIC_API_KEY is unset, "
                            "falling back to rubric")
            return RubricModel()
        from src.model.llm import LLMModel
        return LLMModel()
    return RubricModel()


def main(settings: Settings | None = None) -> None:
    settings = settings or default_settings
    payload = json.loads((settings.processed_dir / "branch_features.json").read_text())
    network = NetworkStats(**payload["network"])
    branches = [BranchFeatures(**b) for b in payload["branches"]]

    model = resolve_backend(settings)
    decisions = model.decide(branches, network)

    (settings.processed_dir / "decisions.json").write_text(
        json.dumps([d.model_dump() for d in decisions], indent=2))

    print(f"model: backend={model.name}, wrote {len(decisions)} decisions")

    rubric_cache = settings.processed_dir / "decisions_rubric.json"
    if model.name == "rubric":
        rubric_cache.write_text(json.dumps([d.model_dump() for d in decisions], indent=2))
    elif rubric_cache.exists():
        rubric_decisions = {d["branch_id"]: d["action"]
                             for d in json.loads(rubric_cache.read_text())}
        llm_decisions = {d.branch_id: d.action for d in decisions}
        agree = sum(1 for bid, action in llm_decisions.items()
                     if rubric_decisions.get(bid) == action)
        print(f"model: llm vs rubric agreement on {agree}/{len(llm_decisions)} branches")
        for bid, action in llm_decisions.items():
            if rubric_decisions.get(bid) != action:
                print(f"  disagreement on {bid}: llm={action} rubric={rubric_decisions.get(bid)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/model/test_run.py -v`
Expected: 3 passed

- [ ] **Step 5: Run stage 3 against real data with the rubric backend (guaranteed no-API-key path)**

Run: `MODEL_BACKEND=rubric uv run python -m src.model.run`
Expected: prints `model: backend=rubric, wrote N decisions`; `data/processed/decisions.json` is valid JSON with one entry per branch.

- [ ] **Step 6: Commit**

```bash
git add src/model/run.py tests/model/test_run.py
git commit -m "Add stage 3 entrypoint with automatic rubric fallback and llm-vs-rubric comparison"
```

---

### Task 13: Wire up the Makefile

**Files:**
- Modify: `Makefile`

**Interfaces:**
- Consumes: entrypoints from Tasks 7, 9, 12, and the FastAPI app from Task 14.

- [ ] **Step 1: Confirm the Makefile from Task 1 already matches the required targets**

The `all`, `serve`, `clean`, `test` targets written in Task 1 already call the exact entrypoints built since (`src.acquire.run`, `src.features.build`, `src.model.run`, `src.serve.app:app`). No code change needed — this step is a verification, not an edit.

- [ ] **Step 2: Run the full pipeline for real with zero env vars set**

Run: `unset ANTHROPIC_API_KEY MODEL_BACKEND && make clean && make all`
Expected: acquire summary prints, features summary prints, `model: MODEL_BACKEND=llm but ANTHROPIC_API_KEY is unset, falling back to rubric` warning prints, then `model: backend=rubric, wrote N decisions`. Exit code 0.

- [ ] **Step 3: Commit only if Step 1 required a fix; otherwise no commit needed for this task**

---

### Task 14: Stage 4 — FastAPI service

**Files:**
- Create: `src/serve/app.py`
- Test: `tests/serve/test_app.py`

**Interfaces:**
- Consumes: `data/processed/branch_features.json`, `data/processed/community_assignment.json`, `data/processed/communities.json`, `data/processed/decisions.json`
- Produces: FastAPI `app` with routes `GET /`, `GET /api/branches`, `GET /api/communities`, `GET /api/network`, `GET /api/health`. `/api/communities` returns assignment rows joined with each community's centroid/name/estimated flag from `communities.json`.

- [ ] **Step 1: Write the failing test**

```python
# tests/serve/test_app.py
import json

import pytest
from httpx import ASGITransport, AsyncClient

from src.config import Settings
from src.serve.app import create_app


def _seed_processed(processed_dir):
    (processed_dir / "branch_features.json").write_text(json.dumps({
        "network": {
            "branch_count": 1, "total_female_population": 1000,
            "female_pop_served_median": 1000, "female_pop_served_p25": 1000,
            "female_pop_served_p75": 1000, "contested_share_median": 0.1,
            "contested_share_p25": 0.1, "contested_share_p75": 0.1,
            "avg_price_aed_median": 100, "avg_price_aed_p25": 100, "avg_price_aed_p75": 100,
            "rating_median": 4.5, "rating_p25": 4.5, "rating_p75": 4.5,
        },
        "branches": [{
            "branch_id": "a", "name": "A", "lat": 25.0, "lng": 55.0, "female_pop_served": 1000,
            "communities_served": 1, "mean_distance_km": 1.0, "max_distance_km": 1.0,
            "contested_pop": 100, "contested_share": 0.1, "nearest_sibling_km": 5.0,
            "siblings_within_5km": 0, "avg_price_aed": 100.0, "price_index": 1.0, "rating": 4.5,
            "review_count": 10, "pop_per_1k_rank": 1, "estimated_fields": [],
        }],
    }))
    (processed_dir / "community_assignment.json").write_text(json.dumps([{
        "community_id": "c1", "nearest_branch_id": "a", "nearest_km": 1.0,
        "second_branch_id": None, "second_km": None, "contested": False, "female_pop": 500,
    }]))
    (processed_dir / "communities.json").write_text(json.dumps([{
        "id": "c1", "name_en": "C1", "lat": 25.05, "lng": 55.15,
        "population_total": 1000, "population_female": 500, "is_estimated": False,
    }]))
    (processed_dir / "decisions.json").write_text(json.dumps([{
        "branch_id": "a", "action": "PROTECT", "confidence": "high",
        "rationale": "Strong branch.", "key_drivers": ["female_pop_served"], "caveats": [],
    }]))


@pytest.fixture
def client(tmp_path):
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    _seed_processed(processed_dir)
    settings = Settings(_env_file=None, processed_dir=processed_dir, model_backend="rubric")
    app = create_app(settings)
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_health(client):
    async with client as c:
        resp = await c.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_branches_joined_with_decisions(client):
    async with client as c:
        resp = await c.get("/api/branches")
    body = resp.json()
    assert body[0]["branch_id"] == "a"
    assert body[0]["action"] == "PROTECT"


async def test_communities_joined_with_centroid(client):
    async with client as c:
        resp = await c.get("/api/communities")
    body = resp.json()
    assert body[0]["community_id"] == "c1"
    assert body[0]["lat"] == 25.05
    assert body[0]["name_en"] == "C1"


async def test_network(client):
    async with client as c:
        resp = await c.get("/api/network")
    body = resp.json()
    assert body["stats"]["branch_count"] == 1
    assert body["model_backend"] == "rubric"


async def test_index_serves_html(client):
    async with client as c:
        resp = await c.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/serve/test_app.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write a minimal placeholder `src/serve/static/index.html` (fleshed out in Task 15)**

```html
<!doctype html>
<html>
  <head><title>Bedashing V0</title></head>
  <body><div id="map"></div></body>
</html>
```

- [ ] **Step 4: Write `src/serve/app.py`**

```python
import datetime
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.config import Settings, settings as default_settings

STATIC_DIR = Path(__file__).parent / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or default_settings
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    def _load(name: str):
        return json.loads((settings.processed_dir / name).read_text())

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/branches")
    def branches():
        features = _load("branch_features.json")["branches"]
        decisions = {d["branch_id"]: d for d in _load("decisions.json")}
        return [{**f, **decisions.get(f["branch_id"], {})} for f in features]

    @app.get("/api/communities")
    def communities():
        assignments = _load("community_assignment.json")
        raw_communities = {c["id"]: c for c in _load("communities.json")}
        merged = []
        for a in assignments:
            c = raw_communities.get(a["community_id"], {})
            merged.append({
                **a,
                "lat": c.get("lat"),
                "lng": c.get("lng"),
                "name_en": c.get("name_en"),
                "is_estimated": c.get("is_estimated"),
            })
        return merged

    @app.get("/api/network")
    def network():
        payload = _load("branch_features.json")
        mtime = (settings.processed_dir / "branch_features.json").stat().st_mtime
        return {
            "stats": payload["network"],
            "model_backend": settings.model_backend,
            "data_sources": {
                "branches": "seed" if not settings.enable_scrape else "seed (scrape unimplemented)",
                "communities": "seed" if not settings.dubai_pulse_enabled
                                else "seed (pulse unimplemented)",
            },
            "pipeline_run_at": datetime.datetime.fromtimestamp(mtime).isoformat(),
        }

    return app


app = create_app()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/serve/test_app.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add src/serve/app.py src/serve/static/index.html tests/serve/test_app.py
git commit -m "Add FastAPI service exposing branches/communities/network endpoints"
```

---

### Task 15: Frontend — Leaflet map, layers, and side panel

**Files:**
- Modify: `src/serve/static/index.html`
- Create: `src/serve/static/app.js`, `src/serve/static/style.css`

**Interfaces:**
- Consumes: `GET /api/branches`, `GET /api/communities`, `GET /api/network`
- Produces: a working map page. No automated tests per the design doc ("no tests beyond smoke tests") — verified manually per Step 4. All dynamic text (branch names, rationale, caveats, key drivers — several of which come from the LLM backend and must be treated as untrusted) is HTML-escaped before insertion; nothing is written via `innerHTML` without passing through `escapeHtml()` first.

- [ ] **Step 1: Write `src/serve/static/index.html`**

```html
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Bedashing V0</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="stylesheet" href="/static/style.css" />
  </head>
  <body>
    <div id="header">
      <span id="backend-label"></span>
      <span id="sources-label"></span>
      <span id="run-at-label"></span>
      <button id="assumptions-toggle">Assumptions</button>
    </div>
    <div id="assumptions-panel" class="hidden">
      <h3>What this V0 is known to get wrong</h3>
      <ol>
        <li>Nearest-branch assignment is false. Real choice depends on travel time, malls, parking, habit, price and brand.</li>
        <li>Community centroids are not where people live. Large communities get collapsed to a point.</li>
        <li>No competitors. A branch with five rival salons next door looks identical to one with none.</li>
        <li>Female population is a poor demand proxy; the skew is spatially concentrated and doesn't capture income, age, or resident-vs-tourist mix.</li>
        <li>No revenue, footfall, staffing or lease data, so SHRINK cannot distinguish a badly-located branch from a badly-run one.</li>
        <li>The LLM classifies without ground truth. Agreement with the rubric is a sanity check, not validation.</li>
        <li>Prices are a thin basket and may not be current.</li>
        <li>Dubai only.</li>
      </ol>
    </div>
    <div id="layer-toggles">
      <label><input type="checkbox" id="toggle-communities" checked /> Communities</label>
      <label><input type="checkbox" id="toggle-assignment-lines" /> Assignment lines</label>
    </div>
    <div id="legend">
      <div><span class="dot protect"></span> PROTECT</div>
      <div><span class="dot hold"></span> HOLD</div>
      <div><span class="dot shrink"></span> SHRINK</div>
    </div>
    <div id="map"></div>
    <div id="side-panel" class="hidden"></div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="/static/app.js"></script>
  </body>
</html>
```

- [ ] **Step 2: Write `src/serve/static/style.css`**

```css
html, body { margin: 0; height: 100%; font-family: sans-serif; }
#map { position: absolute; top: 40px; bottom: 0; left: 0; right: 0; }
#header {
  height: 40px; display: flex; align-items: center; gap: 1rem; padding: 0 1rem;
  background: #222; color: #fff; font-size: 0.85rem;
}
#header button { margin-left: auto; }
#assumptions-panel {
  position: absolute; top: 40px; left: 0; right: 0; z-index: 1000; background: #fff;
  border-bottom: 2px solid #222; padding: 1rem; max-height: 40%; overflow-y: auto;
}
#assumptions-panel.hidden { display: none; }
#layer-toggles {
  position: absolute; top: 50px; right: 10px; z-index: 900; background: #fff;
  padding: 0.5rem; border-radius: 4px; box-shadow: 0 1px 4px rgba(0,0,0,0.3); font-size: 0.85rem;
}
#legend {
  position: absolute; bottom: 20px; left: 10px; z-index: 900; background: #fff;
  padding: 0.5rem; border-radius: 4px; box-shadow: 0 1px 4px rgba(0,0,0,0.3); font-size: 0.85rem;
}
.dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; }
.dot.protect { background: #2e7d32; }
.dot.hold { background: #f9a825; }
.dot.shrink { background: #c62828; }
#side-panel {
  position: absolute; top: 50px; right: 10px; z-index: 950; background: #fff; width: 280px;
  max-height: 70%; overflow-y: auto; padding: 1rem; border-radius: 4px;
  box-shadow: 0 1px 6px rgba(0,0,0,0.4); font-size: 0.85rem;
}
#side-panel.hidden { display: none; }
.estimated { font-style: italic; }
```

- [ ] **Step 3: Write `src/serve/static/app.js`**

Every value that can come from `decisions.json` (i.e. `rationale`, `caveats`, `key_drivers`, `action`, `confidence` — LLM output) or from seed data (`name`) is passed through `escapeHtml()` before being placed in an `innerHTML` template. Numbers used only for `L.circleMarker` options or CSS are safe as-is.

```javascript
const ACTION_COLORS = { PROTECT: "#2e7d32", HOLD: "#f9a825", SHRINK: "#c62828" };

const map = L.map("map").setView([25.2048, 55.2708], 11);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

let branches = [];
let communities = [];
let network = {};
const branchMarkers = {};
let communityLayer = L.layerGroup();
let assignmentLineLayer = L.layerGroup();
let siblingLineLayer = L.layerGroup();

function popRadius(pop) {
  return Math.max(6, Math.min(30, Math.sqrt(pop) / 8));
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value === null || value === undefined ? "" : String(value);
  return div.innerHTML;
}

function fmt(value, isEstimated) {
  if (value === null || value === undefined) return "n/a";
  const text = escapeHtml(typeof value === "number" ? value.toLocaleString() : value);
  return isEstimated ? `<span class="estimated">~${text}</span>` : text;
}

function renderSidePanel(branch) {
  const panel = document.getElementById("side-panel");
  const est = new Set(branch.estimated_fields || []);
  const rows = [
    ["Female population served", branch.female_pop_served, est.has("female_pop_served"), network.female_pop_served_median],
    ["Contested share", branch.contested_share.toFixed(2), est.has("contested_share"), network.contested_share_median?.toFixed(2)],
    ["Avg price (AED)", branch.avg_price_aed, est.has("avg_price_aed"), network.avg_price_aed_median],
    ["Rating", branch.rating, est.has("rating"), network.rating_median],
  ];
  panel.innerHTML = `
    <h3>${escapeHtml(branch.name)}</h3>
    <p><strong>${escapeHtml(branch.action)}</strong> (${escapeHtml(branch.confidence)} confidence)</p>
    <p>${escapeHtml(branch.rationale)}</p>
    <p><strong>Key drivers:</strong> ${escapeHtml((branch.key_drivers || []).join(", "))}</p>
    <table>
      <tr><th>Feature</th><th>Value</th><th>Network median</th></tr>
      ${rows.map(([label, value, isEst, median]) =>
        `<tr><td>${escapeHtml(label)}</td><td>${fmt(value, isEst)}</td><td>${escapeHtml(median ?? "n/a")}</td></tr>`
      ).join("")}
    </table>
    <p><strong>Caveats:</strong> ${escapeHtml((branch.caveats || []).join("; ") || "none")}</p>
  `;
  panel.classList.remove("hidden");
}

function drawSiblingLinks(branch) {
  siblingLineLayer.clearLayers();
  for (const other of branches) {
    if (other.branch_id === branch.branch_id) continue;
    const dLat = branch.lat - other.lat;
    const dLng = branch.lng - other.lng;
    const kmApprox = Math.sqrt(dLat * dLat + dLng * dLng) * 111;
    if (kmApprox <= 5) {
      const line = L.polyline([[branch.lat, branch.lng], [other.lat, other.lng]],
        { color: "#555", weight: 1, dashArray: "4 4" });
      line.bindTooltip(`${kmApprox.toFixed(1)} km`, { permanent: true });
      siblingLineLayer.addLayer(line);
    }
  }
}

function renderBranches() {
  for (const branch of branches) {
    const marker = L.circleMarker([branch.lat, branch.lng], {
      radius: popRadius(branch.female_pop_served),
      color: ACTION_COLORS[branch.action] || "#999",
      fillColor: ACTION_COLORS[branch.action] || "#999",
      fillOpacity: 0.7,
    }).addTo(map);
    marker.bindTooltip(`${escapeHtml(branch.name)} (${escapeHtml(branch.action)})`,
      { permanent: true, direction: "top" });
    marker.on("click", () => {
      renderSidePanel(branch);
      drawSiblingLinks(branch);
      siblingLineLayer.addTo(map);
    });
    branchMarkers[branch.branch_id] = marker;
  }
}

function renderCommunities() {
  const branchById = Object.fromEntries(branches.map(b => [b.branch_id, b]));
  for (const community of communities) {
    const target = branchById[community.nearest_branch_id];
    const color = target ? (ACTION_COLORS[target.action] || "#999") : "#999";
    const dot = L.circleMarker([community.lat ?? 0, community.lng ?? 0], {
      radius: 4, color, fillColor: color,
      fillOpacity: Math.min(1, Math.max(0.2, community.female_pop / 20000)),
    });
    communityLayer.addLayer(dot);

    if (target) {
      const line = L.polyline(
        [[community.lat ?? 0, community.lng ?? 0], [target.lat, target.lng]],
        { color: "#888", weight: 0.5 }
      );
      assignmentLineLayer.addLayer(line);
    }
  }
}

async function main() {
  const [branchResp, communityResp, networkResp] = await Promise.all([
    fetch("/api/branches"), fetch("/api/communities"), fetch("/api/network"),
  ]);
  branches = await branchResp.json();
  communities = await communityResp.json();
  const networkPayload = await networkResp.json();
  network = networkPayload.stats;

  document.getElementById("backend-label").textContent = `backend: ${networkPayload.model_backend}`;
  document.getElementById("sources-label").textContent =
    `sources: branches=${networkPayload.data_sources.branches}, communities=${networkPayload.data_sources.communities}`;
  document.getElementById("run-at-label").textContent = `run at: ${networkPayload.pipeline_run_at}`;

  renderBranches();
  renderCommunities();
  communityLayer.addTo(map);

  document.getElementById("toggle-communities").addEventListener("change", (e) => {
    if (e.target.checked) communityLayer.addTo(map); else map.removeLayer(communityLayer);
  });
  document.getElementById("toggle-assignment-lines").addEventListener("change", (e) => {
    if (e.target.checked) assignmentLineLayer.addTo(map); else map.removeLayer(assignmentLineLayer);
  });
  document.getElementById("assumptions-toggle").addEventListener("click", () => {
    document.getElementById("assumptions-panel").classList.toggle("hidden");
  });
}

main();
```

- [ ] **Step 4: Run the real pipeline and the server, verify manually**

```bash
make clean && make all
make serve
```

Then open `http://localhost:8000` in a browser (or use the `run` skill / browser agent) and confirm: branch markers appear colored by action, clicking a marker opens the side panel with features vs. network medians, the community layer toggles on/off, the assumptions panel toggles, and the header shows backend/sources/run timestamp.

- [ ] **Step 5: Commit**

```bash
git add src/serve/static/index.html src/serve/static/app.js src/serve/static/style.css
git commit -m "Add Leaflet frontend: branch/community layers, side panel, provenance header"
```

---

### Task 16: README and final end-to-end verification

**Files:**
- Modify: `README.md`

**Interfaces:**
- None — this is documentation plus a final verification pass.

- [ ] **Step 1: Write the full `README.md`**

```markdown
# Bedashing V0

A deliberately crude, end-to-end prototype for exploring retail branch decisions
for Bedashing Beauty Lounge (Dubai only). See
`docs/designs/2026-09-24-bedashing-v0-design.md` for the full design and
`docs/designs/2026-09-25-bedashing-v0-plan.md` for how it was built.

## Setup

```bash
uv sync --extra dev
```

## Run everything

```bash
make all     # stages 1-3: acquire -> features -> model
make serve   # http://localhost:8000
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
make test
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
```

- [ ] **Step 2: Run the full test suite one final time**

Run: `uv run pytest -v`
Expected: all tests pass, 0 failures.

- [ ] **Step 3: Run the documented done-state check from the design doc verbatim**

```bash
unset ANTHROPIC_API_KEY
make clean && make all && make serve
```

Expected: Dubai map loads at `http://localhost:8000`, every branch is colored by a rubric-derived action, clicking one shows its features against network medians, and the assumptions list is visible via the toggle.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "Add setup, usage, and known-limitations documentation"
```

---

## Self-Review Notes

- **Spec coverage:** §1 (file-based, idempotent, no-network, DecisionModel interface) → Tasks 1-14. §2 stack → Task 1. §3 layout → File Structure section. §4 acquisition → Tasks 4-7. §5 features → Tasks 8-9. §6 decision model → Tasks 10-12. §7 service → Task 14. §8 frontend → Task 15. §9 assumptions → Task 15 (rendered) + Task 16 (README). §10 build order/Makefile → Tasks 1, 13, 16. §11 (poke-at prompts) is explicitly post-build usage, not implementation — left to the user once the app is running, not a task.
- **Placeholder scan:** no TBD/TODO; the two `NotImplementedError` stubs (live scrape, Dubai Pulse) are real, tested, intentional scope decisions documented up front, not deferred-detail placeholders.
- **Type consistency:** `DecisionModel.decide` takes `list[BranchFeatures]` and returns `list[Decision]` consistently across `base.py` (Task 10), `rubric.py` (Task 10), `llm.py` (Task 11), and `run.py` (Task 12) — this is a deliberate widening from the source doc's per-branch protocol sketch, called out in Task 10.
- **Security fix applied:** original draft of Task 15's `app.js` interpolated `branch.name`/`rationale`/`caveats`/`key_drivers` (LLM-controlled text) directly into `innerHTML`. Fixed by adding `escapeHtml()` and routing every dynamic value through it before template interpolation, and calling this out explicitly in the Global Constraints and Task 15's interface notes so it isn't silently reintroduced during implementation.
- Task 9's `build.py` was corrected to write `data/processed/communities.json` (needed by Task 14/15 to join community centroids) directly rather than deferring it to a later "fix" step, since deferring a required file write across tasks would leave Task 9's tests referencing a file it doesn't produce.
