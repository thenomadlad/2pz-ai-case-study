> **Historical: describes the v1 model; the current model is in the [README](../../README.md).**

# Bedashing V1 Implementation Plan: The Perturbation Loop

> **Executed.** Checkboxes were never ticked. Tasks 10–11 (FastAPI/Leaflet diff mode) were later removed by the Streamlit rebuild, and the LLM backend by v2.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the v1 perturbation loop on top of the existing v0 pipeline — a baseline computed once from an explicit assumptions file, scenarios declared as YAML overrides (including the three example perturbations: a new branch, a relocated branch, a rating change), a diff between baseline and a scenario's result, and a diff-mode overlay on the existing map.

**Architecture:** A new `src/scenario/` package sits *around* the untouched `acquire`/`features`/`model` modules — it loads the fixed baseline raw data, patches it in memory per a scenario's overrides, calls the same pure `build_features`/`RubricModel`/`LLMModel` functions v0 already has, and writes the result to a sibling `data/processed/current/` directory alongside a `diff.json` comparing it to `data/processed/baseline/`. No decisioning or report-shape code changes.

**Tech Stack:** Same as v0 (Python 3.11+, `uv`, FastAPI, pydantic v2, vanilla JS + Leaflet) plus `pyyaml` for scenario/baseline files.

## Global Constraints

- Full design reference: `docs/designs/v1.md`. Read it before starting if anything below is ambiguous — this plan implements it exactly.
- `acquire`/`features`/`model` module internals (file contents beyond the two small parameterization changes in Task 1) are NOT to be touched — the whole point of v1 is that only orchestration changes.
- Baseline is immutable except by deliberately re-running `just all` against new seed data/`baseline.yaml` — there is no "promote current to baseline" step anywhere in this plan.
- `acquire` never re-runs per scenario. Only `contest_ratio` and `model_backend` are perturbable scenario assumptions; `global_female_share`/`fallback_price_aed` are baseline-only (baked into `data/raw/*.json` once).
- Scenario overrides apply in memory only — `data/raw/*.json` is read-only to every scenario run, never written to.
- An override key that matches an existing baseline id is a **patch** (partial fields). An override key that doesn't match an existing id is a **new entity** and must supply enough fields to construct a complete `Branch`/`Community` — pydantic validation failure on a new-entity construction is the designed signal for "you probably meant to patch an existing id and typo'd it."
- `model_backend: rubric` is the recommended default for scenario runs (free, instant, deterministic) — `baseline.yaml` keeps `model_backend: llm` to match v0's existing documented default and zero-API-key fallback behavior.
- Scenario/baseline files live under `data/scenarios/` (sibling of `data/seed/`), loaded relative to `settings.seed_dir.parent`.
- Directory convention: `data/raw/*.json` (shared, unprefixed, produced once). `data/processed/baseline/*.json` (produced once by `just all`). `data/processed/current/*.json` + `diff.json` (produced fresh by every `just scenario <path>` run, fully overwritten each time).
- `Settings.processed_dir`'s default changes from `data/processed` to `data/processed/baseline` — this is safe because every existing test that cares about `processed_dir` already constructs `Settings(processed_dir=...)` explicitly, overriding the default.
- Frontend: every dynamic value reaching `innerHTML` must go through the existing `escapeHtml()`/`fmt()` helpers, with no exceptions — this includes the new diff-section rendering in Task 11, which routes every interpolated value through a dedicated `formatChangedFieldRow()` helper that calls `escapeHtml()` on each piece before building the row string.

---

## File Structure

```
2pz-ai-case-study/
  pyproject.toml              # +pyyaml dependency
  justfile                     # `all` -> new baseline entrypoint; +`scenario` recipe
  data/
    scenarios/
      baseline.yaml             # new
      example-perturbations.yaml # new — the 3 requested example perturbations
    raw/                        # unchanged location, unprefixed (shared)
    processed/
      baseline/                  # was data/processed/ directly in v0
      current/                    # new — scenario output + diff.json
  src/
    config.py                     # +global_female_share, +fallback_price_aed, processed_dir default change
    models.py                      # Branch.source literal gains "scenario"
    acquire/
      population.py                 # load() reads settings.global_female_share, drops the param
      prices.py                      # backfill_missing_prices() gains fallback_price_aed param
      run.py                          # passes settings.fallback_price_aed through
    scenario/
      __init__.py
      models.py                        # BaselineAssumptions, ScenarioAssumptions, Scenario,
                                         # ScenarioOverrides, BranchDiffEntry, CommunityDiffEntry,
                                         # ScenarioDiff
      baseline.py                       # load_baseline_assumptions(), main() -> runs acquire+
                                         # features+model with baseline.yaml's assumptions
      load.py                            # load_scenario(path) -> Scenario
      apply.py                            # apply_branch_overrides, apply_community_overrides
      diff.py                              # compute_branch_diff, compute_community_diff
      run.py                                # main(scenario_path, settings=None) orchestrator
    serve/
      app.py                                 # +GET /api/diff
      static/
        index.html                            # +diff toggle checkbox
        app.js                                  # diff fetch, highlight layer, side-panel diff section
        style.css                                # +diff-section styling
  tests/
    test_config.py                 # +global_female_share/fallback_price_aed/processed_dir assertions
    test_models.py                  # Branch.source "scenario" test
    acquire/
      test_population.py              # signature update
      test_prices.py                   # +fallback_price_aed param test
      test_run.py                       # unchanged (default behavior preserved)
    scenario/
      __init__.py
      test_models.py
      test_baseline.py
      test_load.py
      test_apply.py
      test_diff.py
      test_run.py
      test_example_scenario.py           # real end-to-end check against real seed data
    serve/
      test_app.py                          # fixture nests under baseline/; +diff endpoint tests
```

---

### Task 1: Settings & acquire-stage parameterization

**Files:**
- Modify: `src/config.py`
- Modify: `src/models.py`
- Modify: `src/acquire/population.py`
- Modify: `src/acquire/prices.py`
- Modify: `src/acquire/run.py`
- Modify: `tests/test_config.py`
- Modify: `tests/test_models.py`
- Modify: `tests/acquire/test_population.py`

**Interfaces:**
- Produces: `Settings.global_female_share: float` (default `0.49`), `Settings.fallback_price_aed: float` (default `99.0`), `Settings.processed_dir` default now `REPO_ROOT/data/processed/baseline`. `population.load(settings=None) -> list[Community]` (no more `global_female_share` param). `backfill_missing_prices(branches, fallback_price_aed=FALLBACK_PRICE_AED) -> tuple[list[Branch], list[str]]`. `Branch.source` now `Literal["seed", "fresha", "places", "scenario"]`.

- [ ] **Step 1: Update `src/config.py`**

```python
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    seed_dir: Path = REPO_ROOT / "data" / "seed"
    raw_dir: Path = REPO_ROOT / "data" / "raw"
    processed_dir: Path = REPO_ROOT / "data" / "processed" / "baseline"

    enable_scrape: bool = False
    dubai_pulse_enabled: bool = False
    model_backend: Literal["llm", "rubric"] = "llm"
    contest_ratio: float = 1.25
    global_female_share: float = 0.49
    fallback_price_aed: float = 99.0
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-haiku-4-5-20251001"


settings = Settings()
```

- [ ] **Step 2: Update `src/models.py`'s `Branch.source` field**

Change the `Branch` class's `source` field from:
```python
    source: Literal["seed", "fresha", "places"]
```
to:
```python
    source: Literal["seed", "fresha", "places", "scenario"]
```

- [ ] **Step 3: Update `src/acquire/population.py`'s `load()` to drop the parameter**

Change:
```python
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
to:
```python
def load(settings: Settings | None = None) -> list[Community]:
    settings = settings or default_settings
    if settings.dubai_pulse_enabled:
        try:
            return _fetch_dubai_pulse()
        except NotImplementedError:
            logger.warning("population: DUBAI_PULSE_ENABLED=1 but live enrichment isn't "
                            "implemented in V0, falling back to seed")
    return _load_seed(settings.seed_dir, settings.global_female_share)
```

- [ ] **Step 4: Update `tests/acquire/test_population.py`'s call site**

In `test_load_estimates_missing_female_population`, change:
```python
    result = population.load(test_settings, global_female_share=0.49)
```
to:
```python
    result = population.load(test_settings)
```
(unchanged expected values — `Settings`'s default `global_female_share` is already `0.49`, matching the test's `490` expectation for `1000 * 0.49`.)

- [ ] **Step 5: Update `src/acquire/prices.py` to accept a fallback parameter**

Change:
```python
def backfill_missing_prices(branches: list[Branch]) -> tuple[list[Branch], list[str]]:
    known = [b.avg_price_aed for b in branches if b.avg_price_aed is not None]
    if not known:
        # All branches missing prices: apply fallback and flag all
        result = [b.model_copy(update={"avg_price_aed": FALLBACK_PRICE_AED}) for b in branches]
        flagged = [b.id for b in branches]
        return result, flagged
```
to:
```python
def backfill_missing_prices(
    branches: list[Branch], fallback_price_aed: float = FALLBACK_PRICE_AED,
) -> tuple[list[Branch], list[str]]:
    known = [b.avg_price_aed for b in branches if b.avg_price_aed is not None]
    if not known:
        # All branches missing prices: apply fallback and flag all
        result = [b.model_copy(update={"avg_price_aed": fallback_price_aed}) for b in branches]
        flagged = [b.id for b in branches]
        return result, flagged
```
(rest of the function unchanged — the median-of-known-prices branch doesn't use the fallback constant at all).

- [ ] **Step 6: Update `src/acquire/run.py` to pass the setting through**

Change:
```python
    filled_branches, price_flags = backfill_missing_prices(raw_branches)
```
to:
```python
    filled_branches, price_flags = backfill_missing_prices(raw_branches, settings.fallback_price_aed)
```

- [ ] **Step 7: Add test assertions to `tests/test_config.py`**

Add to `test_defaults` (after the existing assertions, before the function ends):
```python
    assert s.global_female_share == 0.49
    assert s.fallback_price_aed == 99.0
    from src.config import REPO_ROOT
    assert s.processed_dir == REPO_ROOT / "data" / "processed" / "baseline"
```

- [ ] **Step 8: Add a test for the new `Branch.source` value to `tests/test_models.py`**

Add a new test function:
```python
def test_branch_accepts_scenario_source():
    b = Branch(id="new-branch", name="New Branch", lat=25.0, lng=55.0, area="Somewhere",
               rating=None, review_count=None, avg_price_aed=None, source="scenario")
    assert b.source == "scenario"
```

- [ ] **Step 9: Run the affected test files**

Run: `uv run pytest tests/test_config.py tests/test_models.py tests/acquire/ -v`
Expected: all pass, including the existing `tests/acquire/test_prices.py` and `tests/acquire/test_run.py` tests (unchanged — their expected values match the new defaults).

- [ ] **Step 10: Run the full suite to confirm no regressions**

Run: `uv run pytest -q`
Expected: 59 passed (58 pre-existing + 1 new `test_branch_accepts_scenario_source`; `test_defaults` gained assertions but is still one test).

- [ ] **Step 11: Commit**

```bash
git add src/config.py src/models.py src/acquire/population.py src/acquire/prices.py src/acquire/run.py tests/test_config.py tests/test_models.py tests/acquire/test_population.py
git commit -m "Parameterize acquire-stage assumptions via Settings; widen Branch.source for scenarios"
```

---

### Task 2: `pyyaml` dependency + scenario domain models

**Files:**
- Modify: `pyproject.toml`
- Create: `src/scenario/__init__.py`
- Create: `src/scenario/models.py`
- Test: `tests/scenario/__init__.py`, `tests/scenario/test_models.py`

**Interfaces:**
- Produces: `BaselineAssumptions`, `ScenarioAssumptions`, `ScenarioOverrides`, `Scenario`, `BranchDiffEntry`, `CommunityDiffEntry`, `ScenarioDiff` — imported by every later scenario task.

- [ ] **Step 1: Add `pyyaml` to `pyproject.toml`**

In the `dependencies` list, add `"pyyaml>=6.0",` (after `"anthropic>=0.34",`).

- [ ] **Step 2: Write the failing tests**

```python
# tests/scenario/__init__.py
```

```python
# tests/scenario/test_models.py
import pytest
from pydantic import ValidationError

from src.scenario.models import (
    BaselineAssumptions, ScenarioAssumptions, ScenarioOverrides, Scenario,
    BranchDiffEntry, CommunityDiffEntry, ScenarioDiff,
)


def test_baseline_assumptions_defaults():
    a = BaselineAssumptions()
    assert a.contest_ratio == 1.25
    assert a.global_female_share == 0.49
    assert a.fallback_price_aed == 99.0
    assert a.model_backend == "llm"


def test_baseline_assumptions_rejects_unknown_field():
    with pytest.raises(ValidationError):
        BaselineAssumptions(continue_ratio=1.1)  # typo'd field name


def test_scenario_assumptions_default_to_none():
    a = ScenarioAssumptions()
    assert a.contest_ratio is None
    assert a.model_backend is None


def test_scenario_minimal():
    s = Scenario(name="test-scenario")
    assert s.name == "test-scenario"
    assert s.assumptions.contest_ratio is None
    assert s.overrides.branches == {}
    assert s.overrides.communities == {}


def test_scenario_with_overrides():
    s = Scenario(name="test", overrides=ScenarioOverrides(
        branches={"al-safa-2": {"lat": 25.27, "lng": 55.31}},
        communities={"deira": {"population_female": 9000}},
    ))
    assert s.overrides.branches["al-safa-2"]["lat"] == 25.27
    assert s.overrides.communities["deira"]["population_female"] == 9000


def test_branch_diff_entry_new_branch_has_no_old():
    entry = BranchDiffEntry(branch_id="new-one", old=None, new={"action": "PROTECT"},
                             changed_fields={}, action_changed=True)
    assert entry.old is None
    assert entry.new["action"] == "PROTECT"


def test_community_diff_entry_reassigned():
    entry = CommunityDiffEntry(community_id="c1", reassigned=True,
                                old_branch_id="a", new_branch_id="b")
    assert entry.reassigned is True


def test_scenario_diff_shape():
    diff = ScenarioDiff(scenario_name="x", branches=[], communities=[])
    assert diff.scenario_name == "x"
    assert diff.branches == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/scenario/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.scenario'`

- [ ] **Step 4: Write `src/scenario/__init__.py`**

```python
```
(empty file)

- [ ] **Step 5: Write `src/scenario/models.py`**

```python
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class BaselineAssumptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contest_ratio: float = 1.25
    global_female_share: float = 0.49
    fallback_price_aed: float = 99.0
    model_backend: Literal["llm", "rubric"] = "llm"


class ScenarioAssumptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contest_ratio: float | None = None
    model_backend: Literal["llm", "rubric"] | None = None


class ScenarioOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branches: dict[str, dict[str, Any]] = {}
    communities: dict[str, dict[str, Any]] = {}


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    assumptions: ScenarioAssumptions = ScenarioAssumptions()
    overrides: ScenarioOverrides = ScenarioOverrides()


class BranchDiffEntry(BaseModel):
    branch_id: str
    old: dict[str, Any] | None
    new: dict[str, Any] | None
    changed_fields: dict[str, dict[str, Any]]
    action_changed: bool


class CommunityDiffEntry(BaseModel):
    community_id: str
    reassigned: bool
    old_branch_id: str | None
    new_branch_id: str | None


class ScenarioDiff(BaseModel):
    scenario_name: str
    branches: list[BranchDiffEntry]
    communities: list[CommunityDiffEntry]
```

- [ ] **Step 6: Install the new dependency and run tests**

Run: `uv sync --extra dev && uv run pytest tests/scenario/test_models.py -v`
Expected: 8 passed

- [ ] **Step 7: Run the full suite**

Run: `uv run pytest -q`
Expected: 67 passed (59 + 8 new)

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock src/scenario/__init__.py src/scenario/models.py tests/scenario/__init__.py tests/scenario/test_models.py
git commit -m "Add scenario domain models and pyyaml dependency"
```

---

### Task 3: Baseline loader and orchestrator

**Files:**
- Create: `src/scenario/baseline.py`
- Create: `data/scenarios/baseline.yaml`
- Test: `tests/scenario/test_baseline.py`

**Interfaces:**
- Consumes: `src.scenario.models.BaselineAssumptions`, `src.acquire.run.main`, `src.features.build.main`, `src.model.run.main`
- Produces: `load_baseline_assumptions(path) -> BaselineAssumptions`; `main(settings=None) -> None`

- [ ] **Step 1: Write the failing tests**

```python
# tests/scenario/test_baseline.py
from unittest.mock import MagicMock

import yaml

from src.scenario.baseline import load_baseline_assumptions, main
from src.config import Settings


def test_load_baseline_assumptions_from_yaml(tmp_path):
    path = tmp_path / "baseline.yaml"
    path.write_text(yaml.dump({
        "assumptions": {
            "contest_ratio": 1.3,
            "global_female_share": 0.52,
            "fallback_price_aed": 110.0,
            "model_backend": "rubric",
        }
    }))

    assumptions = load_baseline_assumptions(path)

    assert assumptions.contest_ratio == 1.3
    assert assumptions.global_female_share == 0.52
    assert assumptions.fallback_price_aed == 110.0
    assert assumptions.model_backend == "rubric"


def test_load_baseline_assumptions_defaults_when_file_sparse(tmp_path):
    path = tmp_path / "baseline.yaml"
    path.write_text(yaml.dump({"assumptions": {"contest_ratio": 1.1}}))

    assumptions = load_baseline_assumptions(path)

    assert assumptions.contest_ratio == 1.1
    assert assumptions.global_female_share == 0.49  # BaselineAssumptions default


def test_main_calls_all_three_stages_with_baseline_settings(tmp_path, monkeypatch):
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "baseline.yaml").write_text(yaml.dump({
        "assumptions": {"contest_ratio": 1.4, "model_backend": "rubric"},
    }))

    test_settings = Settings(_env_file=None, seed_dir=tmp_path / "seed")

    mock_acquire = MagicMock()
    mock_features = MagicMock()
    mock_model = MagicMock()
    monkeypatch.setattr("src.scenario.baseline.acquire_run.main", mock_acquire)
    monkeypatch.setattr("src.scenario.baseline.features_build.main", mock_features)
    monkeypatch.setattr("src.scenario.baseline.model_run.main", mock_model)

    main(test_settings)

    mock_acquire.assert_called_once()
    mock_features.assert_called_once()
    mock_model.assert_called_once()
    called_settings = mock_acquire.call_args[0][0]
    assert called_settings.contest_ratio == 1.4
    assert called_settings.model_backend == "rubric"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/scenario/test_baseline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.scenario.baseline'`

- [ ] **Step 3: Write `src/scenario/baseline.py`**

```python
import yaml

from src.acquire import run as acquire_run
from src.config import Settings, settings as default_settings
from src.features import build as features_build
from src.model import run as model_run
from src.scenario.models import BaselineAssumptions


def load_baseline_assumptions(path) -> BaselineAssumptions:
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return BaselineAssumptions(**data.get("assumptions", {}))


def main(settings: Settings | None = None) -> None:
    settings = settings or default_settings
    scenarios_dir = settings.seed_dir.parent / "scenarios"
    assumptions = load_baseline_assumptions(scenarios_dir / "baseline.yaml")

    baseline_settings = settings.model_copy(update={
        "contest_ratio": assumptions.contest_ratio,
        "global_female_share": assumptions.global_female_share,
        "fallback_price_aed": assumptions.fallback_price_aed,
        "model_backend": assumptions.model_backend,
    })

    acquire_run.main(baseline_settings)
    features_build.main(baseline_settings)
    model_run.main(baseline_settings)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Write `data/scenarios/baseline.yaml`**

```yaml
# Baseline assumptions -- "reality". Edit this file and re-run `just all` to
# regenerate the one true baseline raw data and report. Never edited by a
# scenario run.
assumptions:
  contest_ratio: 1.25
  global_female_share: 0.49
  fallback_price_aed: 99.0
  model_backend: llm
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/scenario/test_baseline.py -v`
Expected: 3 passed

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest -q`
Expected: 70 passed (67 + 3 new)

- [ ] **Step 7: Commit**

```bash
git add src/scenario/baseline.py data/scenarios/baseline.yaml tests/scenario/test_baseline.py
git commit -m "Add baseline assumptions loader and orchestrator"
```

---

### Task 4: Scenario loader

**Files:**
- Create: `src/scenario/load.py`
- Test: `tests/scenario/test_load.py`

**Interfaces:**
- Consumes: `src.scenario.models.Scenario`
- Produces: `load_scenario(path) -> Scenario`

- [ ] **Step 1: Write the failing tests**

```python
# tests/scenario/test_load.py
import pytest
import yaml
from pydantic import ValidationError

from src.scenario.load import load_scenario


def test_load_scenario_full(tmp_path):
    path = tmp_path / "test-scenario.yaml"
    path.write_text(yaml.dump({
        "name": "bigger-palm-jumeirah",
        "assumptions": {"contest_ratio": 1.1},
        "overrides": {
            "branches": {
                "palm-jumeirah": {"rating": 4.9},
                "hypothetical-marina": {
                    "name": "Hypothetical Marina", "lat": 25.08, "lng": 55.14, "area": "Marina",
                },
            },
            "communities": {
                "al-sufouh-second": {"population_female": 9000},
            },
        },
    }))

    scenario = load_scenario(path)

    assert scenario.name == "bigger-palm-jumeirah"
    assert scenario.assumptions.contest_ratio == 1.1
    assert scenario.overrides.branches["palm-jumeirah"]["rating"] == 4.9
    assert scenario.overrides.branches["hypothetical-marina"]["area"] == "Marina"
    assert scenario.overrides.communities["al-sufouh-second"]["population_female"] == 9000


def test_load_scenario_minimal(tmp_path):
    path = tmp_path / "minimal.yaml"
    path.write_text(yaml.dump({"name": "noop"}))

    scenario = load_scenario(path)

    assert scenario.name == "noop"
    assert scenario.overrides.branches == {}


def test_load_scenario_rejects_unknown_top_level_field(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.dump({"name": "bad", "asumptions": {"contest_ratio": 1.1}}))  # typo

    with pytest.raises(ValidationError):
        load_scenario(path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/scenario/test_load.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.scenario.load'`

- [ ] **Step 3: Write `src/scenario/load.py`**

```python
import yaml

from src.scenario.models import Scenario


def load_scenario(path) -> Scenario:
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return Scenario(**data)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/scenario/test_load.py -v`
Expected: 3 passed

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: 73 passed (70 + 3 new)

- [ ] **Step 6: Commit**

```bash
git add src/scenario/load.py tests/scenario/test_load.py
git commit -m "Add scenario YAML loader with strict validation"
```

---

### Task 5: Override application

**Files:**
- Create: `src/scenario/apply.py`
- Test: `tests/scenario/test_apply.py`

**Interfaces:**
- Consumes: `src.models.Branch`, `src.models.Community`
- Produces: `apply_branch_overrides(branches: list[Branch], overrides: dict[str, dict]) -> list[Branch]`; `apply_community_overrides(communities: list[Community], overrides: dict[str, dict]) -> list[Community]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/scenario/test_apply.py
import pytest
from pydantic import ValidationError

from src.models import Branch, Community
from src.scenario.apply import apply_branch_overrides, apply_community_overrides


def _branch(id_, lat=25.0, lng=55.0, rating=4.5):
    return Branch(id=id_, name=f"Branch {id_}", lat=lat, lng=lng, area="Area",
                  rating=rating, review_count=100, avg_price_aed=99.0, source="seed")


def _community(id_, population_total=1000, population_female=490):
    return Community(id=id_, name_en=f"Community {id_}", lat=25.0, lng=55.0,
                      population_total=population_total, population_female=population_female,
                      is_estimated=False)


def test_patch_existing_branch_only_changes_given_fields():
    branches = [_branch("a", rating=4.5), _branch("b", rating=4.0)]
    result = apply_branch_overrides(branches, {"a": {"rating": 4.9}})

    by_id = {b.id: b for b in result}
    assert by_id["a"].rating == 4.9
    assert by_id["a"].lat == 25.0  # unchanged
    assert by_id["b"].rating == 4.0  # untouched


def test_patch_existing_branch_location():
    branches = [_branch("a", lat=25.0, lng=55.0)]
    result = apply_branch_overrides(branches, {"a": {"lat": 25.27, "lng": 55.31}})

    assert result[0].lat == 25.27
    assert result[0].lng == 55.31


def test_new_branch_inserted_with_defaults():
    branches = [_branch("a")]
    result = apply_branch_overrides(branches, {
        "new-one": {"name": "New One", "lat": 25.1, "lng": 55.1, "area": "Somewhere"},
    })

    assert len(result) == 2
    new_branch = next(b for b in result if b.id == "new-one")
    assert new_branch.name == "New One"
    assert new_branch.rating is None  # defaulted
    assert new_branch.source == "scenario"  # defaulted


def test_new_branch_missing_required_field_raises():
    branches = [_branch("a")]
    with pytest.raises(ValidationError):
        apply_branch_overrides(branches, {"new-one": {"rating": 4.9}})  # no name/lat/lng/area


def test_patch_existing_community():
    communities = [_community("c1", population_female=490)]
    result = apply_community_overrides(communities, {"c1": {"population_female": 9000}})

    assert result[0].population_female == 9000
    assert result[0].is_estimated is False  # unchanged


def test_new_community_inserted_with_defaults():
    communities = [_community("c1")]
    result = apply_community_overrides(communities, {
        "new-c": {"name_en": "New Community", "lat": 25.1, "lng": 55.1, "population_total": 5000},
    })

    assert len(result) == 2
    new_community = next(c for c in result if c.id == "new-c")
    assert new_community.population_female is None
    assert new_community.is_estimated is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/scenario/test_apply.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.scenario.apply'`

- [ ] **Step 3: Write `src/scenario/apply.py`**

```python
from src.models import Branch, Community

_BRANCH_NEW_DEFAULTS = {
    "rating": None, "review_count": None, "avg_price_aed": None, "source": "scenario",
}
_COMMUNITY_NEW_DEFAULTS = {"population_female": None, "is_estimated": False}


def apply_branch_overrides(branches: list[Branch], overrides: dict[str, dict]) -> list[Branch]:
    by_id = {b.id: i for i, b in enumerate(branches)}
    result = list(branches)
    for branch_id, patch in overrides.items():
        if branch_id in by_id:
            idx = by_id[branch_id]
            result[idx] = result[idx].model_copy(update=patch)
        else:
            result.append(Branch(id=branch_id, **{**_BRANCH_NEW_DEFAULTS, **patch}))
    return result


def apply_community_overrides(
    communities: list[Community], overrides: dict[str, dict],
) -> list[Community]:
    by_id = {c.id: i for i, c in enumerate(communities)}
    result = list(communities)
    for community_id, patch in overrides.items():
        if community_id in by_id:
            idx = by_id[community_id]
            result[idx] = result[idx].model_copy(update=patch)
        else:
            result.append(Community(id=community_id, **{**_COMMUNITY_NEW_DEFAULTS, **patch}))
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/scenario/test_apply.py -v`
Expected: 7 passed

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: 80 passed (73 + 7 new)

- [ ] **Step 6: Commit**

```bash
git add src/scenario/apply.py tests/scenario/test_apply.py
git commit -m "Add override application: patch-vs-new disambiguation via pydantic validation"
```

---

### Task 6: Diff computation

**Files:**
- Create: `src/scenario/diff.py`
- Test: `tests/scenario/test_diff.py`

**Interfaces:**
- Consumes: `src.models.BranchFeatures`, `src.models.Decision`, `src.models.CommunityAssignment`, `src.scenario.models.BranchDiffEntry/CommunityDiffEntry`
- Produces: `compute_branch_diff(baseline_features, baseline_decisions, current_features, current_decisions) -> list[BranchDiffEntry]`; `compute_community_diff(baseline_assignments, current_assignments) -> list[CommunityDiffEntry]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/scenario/test_diff.py
from src.models import BranchFeatures, CommunityAssignment, Decision
from src.scenario.diff import compute_branch_diff, compute_community_diff


def _features(branch_id, rating=4.5, female_pop_served=1000):
    return BranchFeatures(
        branch_id=branch_id, name=branch_id, lat=25.0, lng=55.0,
        female_pop_served=female_pop_served, communities_served=1, mean_distance_km=1.0,
        max_distance_km=1.0, contested_pop=0, contested_share=0.0, nearest_sibling_km=5.0,
        siblings_within_5km=0, avg_price_aed=99.0, price_index=1.0, rating=rating,
        review_count=10, pop_per_1k_rank=1, estimated_fields=[],
    )


def _decision(branch_id, action="PROTECT"):
    return Decision(branch_id=branch_id, action=action, confidence="medium",
                     rationale="x", key_drivers=[], caveats=[])


def test_branch_diff_detects_changed_field():
    baseline_features = [_features("a", rating=4.5)]
    current_features = [_features("a", rating=3.9)]
    baseline_decisions = [_decision("a", "PROTECT")]
    current_decisions = [_decision("a", "PROTECT")]

    entries = compute_branch_diff(baseline_features, baseline_decisions,
                                   current_features, current_decisions)

    assert len(entries) == 1
    assert entries[0].branch_id == "a"
    assert entries[0].changed_fields["rating"] == {"old": 4.5, "new": 3.9}
    assert entries[0].action_changed is False
    assert entries[0].old is not None
    assert entries[0].new is not None


def test_branch_diff_detects_action_change():
    baseline_features = [_features("a")]
    current_features = [_features("a")]
    entries = compute_branch_diff(baseline_features, [_decision("a", "PROTECT")],
                                   current_features, [_decision("a", "SHRINK")])

    assert entries[0].action_changed is True
    assert entries[0].old["action"] == "PROTECT"
    assert entries[0].new["action"] == "SHRINK"


def test_branch_diff_new_branch_has_no_old():
    entries = compute_branch_diff([], [], [_features("new-one")], [_decision("new-one")])

    assert len(entries) == 1
    assert entries[0].old is None
    assert entries[0].new is not None
    assert entries[0].action_changed is True  # None -> an action is a change


def test_branch_diff_no_changes_when_identical():
    features = [_features("a")]
    decisions = [_decision("a")]
    entries = compute_branch_diff(features, decisions, features, decisions)

    assert entries[0].changed_fields == {}
    assert entries[0].action_changed is False


def test_community_diff_detects_reassignment():
    baseline = [CommunityAssignment(community_id="c1", nearest_branch_id="a", nearest_km=1.0,
                                     second_branch_id=None, second_km=None, contested=False,
                                     female_pop=500)]
    current = [CommunityAssignment(community_id="c1", nearest_branch_id="b", nearest_km=2.0,
                                    second_branch_id=None, second_km=None, contested=False,
                                    female_pop=500)]

    entries = compute_community_diff(baseline, current)

    assert len(entries) == 1
    assert entries[0].reassigned is True
    assert entries[0].old_branch_id == "a"
    assert entries[0].new_branch_id == "b"


def test_community_diff_no_reassignment():
    assignment = CommunityAssignment(community_id="c1", nearest_branch_id="a", nearest_km=1.0,
                                      second_branch_id=None, second_km=None, contested=False,
                                      female_pop=500)
    entries = compute_community_diff([assignment], [assignment])

    assert entries[0].reassigned is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/scenario/test_diff.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.scenario.diff'`

- [ ] **Step 3: Write `src/scenario/diff.py`**

```python
from src.models import BranchFeatures, CommunityAssignment, Decision
from src.scenario.models import BranchDiffEntry, CommunityDiffEntry


def _merge(features: BranchFeatures, decision: Decision | None) -> dict:
    merged = features.model_dump()
    if decision is not None:
        merged.update(decision.model_dump())
    return merged


def compute_branch_diff(
    baseline_features: list[BranchFeatures], baseline_decisions: list[Decision],
    current_features: list[BranchFeatures], current_decisions: list[Decision],
) -> list[BranchDiffEntry]:
    baseline_features_by_id = {f.branch_id: f for f in baseline_features}
    current_features_by_id = {f.branch_id: f for f in current_features}
    baseline_decisions_by_id = {d.branch_id: d for d in baseline_decisions}
    current_decisions_by_id = {d.branch_id: d for d in current_decisions}

    entries = []
    for branch_id in sorted(set(baseline_features_by_id) | set(current_features_by_id)):
        old_features = baseline_features_by_id.get(branch_id)
        new_features = current_features_by_id.get(branch_id)
        old = _merge(old_features, baseline_decisions_by_id.get(branch_id)) if old_features else None
        new = _merge(new_features, current_decisions_by_id.get(branch_id)) if new_features else None

        changed_fields: dict[str, dict] = {}
        if old_features is not None and new_features is not None:
            for field in BranchFeatures.model_fields:
                if field == "branch_id":
                    continue
                old_val = getattr(old_features, field)
                new_val = getattr(new_features, field)
                if old_val != new_val:
                    changed_fields[field] = {"old": old_val, "new": new_val}

        old_action = old.get("action") if old else None
        new_action = new.get("action") if new else None

        entries.append(BranchDiffEntry(
            branch_id=branch_id, old=old, new=new,
            changed_fields=changed_fields, action_changed=old_action != new_action,
        ))
    return entries


def compute_community_diff(
    baseline_assignments: list[CommunityAssignment], current_assignments: list[CommunityAssignment],
) -> list[CommunityDiffEntry]:
    baseline_by_id = {a.community_id: a for a in baseline_assignments}
    current_by_id = {a.community_id: a for a in current_assignments}

    entries = []
    for community_id in sorted(set(baseline_by_id) | set(current_by_id)):
        old = baseline_by_id.get(community_id)
        new = current_by_id.get(community_id)
        old_branch_id = old.nearest_branch_id if old else None
        new_branch_id = new.nearest_branch_id if new else None
        entries.append(CommunityDiffEntry(
            community_id=community_id,
            reassigned=old_branch_id != new_branch_id,
            old_branch_id=old_branch_id,
            new_branch_id=new_branch_id,
        ))
    return entries
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/scenario/test_diff.py -v`
Expected: 6 passed

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: 86 passed (80 + 6 new)

- [ ] **Step 6: Commit**

```bash
git add src/scenario/diff.py tests/scenario/test_diff.py
git commit -m "Add branch and community diff computation"
```

---

### Task 7: Scenario run orchestrator

**Files:**
- Create: `src/scenario/run.py`
- Test: `tests/scenario/test_run.py`

**Interfaces:**
- Consumes: `load_scenario`, `apply_branch_overrides`, `apply_community_overrides`, `build_features`, `resolve_backend`, `compute_branch_diff`, `compute_community_diff`, `load_baseline_assumptions`
- Produces: `main(scenario_path, settings=None) -> None`, writing `data/processed/current/{branch_features,community_assignment,communities,decisions,run_meta,diff}.json`

- [ ] **Step 1: Write the failing test**

```python
# tests/scenario/test_run.py
import csv
import json

import yaml

from src.config import Settings
from src.scenario.run import main


def _write_seed_and_baseline(tmp_path):
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    with open(seed_dir / "branches.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "id", "name", "lat", "lng", "area", "rating", "review_count", "avg_price_aed"])
        w.writeheader()
        w.writerow({"id": "a", "name": "A", "lat": "25.10", "lng": "55.20", "area": "Area A",
                    "rating": "4.5", "review_count": "100", "avg_price_aed": "99"})
        w.writerow({"id": "b", "name": "B", "lat": "25.50", "lng": "55.50", "area": "Area B",
                    "rating": "4.0", "review_count": "50", "avg_price_aed": "99"})
    with open(seed_dir / "communities.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "id", "name_en", "lat", "lng", "population_total", "population_female"])
        w.writeheader()
        w.writerow({"id": "c1", "name_en": "C1", "lat": "25.11", "lng": "55.21",
                    "population_total": "1000", "population_female": "490"})

    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "baseline.yaml").write_text(yaml.dump({
        "assumptions": {"contest_ratio": 1.25, "model_backend": "rubric"},
    }))

    raw_dir = tmp_path / "raw"
    baseline_dir = tmp_path / "processed" / "baseline"

    from src.scenario.baseline import main as baseline_main
    baseline_settings = Settings(_env_file=None, seed_dir=seed_dir, raw_dir=raw_dir,
                                  processed_dir=baseline_dir)
    baseline_main(baseline_settings)
    return seed_dir, raw_dir, baseline_dir, scenarios_dir


def test_scenario_run_writes_current_and_diff(tmp_path):
    seed_dir, raw_dir, baseline_dir, scenarios_dir = _write_seed_and_baseline(tmp_path)

    scenario_path = scenarios_dir / "test-scenario.yaml"
    scenario_path.write_text(yaml.dump({
        "name": "test-scenario",
        "assumptions": {"model_backend": "rubric"},
        "overrides": {
            "branches": {
                "a": {"rating": 3.0},
                "new-branch": {"name": "New Branch", "lat": 25.3, "lng": 55.3, "area": "New Area"},
            },
        },
    }))

    settings = Settings(_env_file=None, seed_dir=seed_dir, raw_dir=raw_dir,
                         processed_dir=baseline_dir)
    main(scenario_path, settings)

    current_dir = baseline_dir.parent / "current"
    features = json.loads((current_dir / "branch_features.json").read_text())
    assert len(features["branches"]) == 3  # a, b, new-branch

    diff = json.loads((current_dir / "diff.json").read_text())
    assert diff["scenario_name"] == "test-scenario"
    by_id = {b["branch_id"]: b for b in diff["branches"]}
    assert by_id["a"]["changed_fields"]["rating"] == {"old": 4.5, "new": 3.0}
    assert by_id["new-branch"]["old"] is None
    assert by_id["new-branch"]["action_changed"] is True


def test_scenario_run_raises_when_baseline_missing(tmp_path):
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "baseline.yaml").write_text(yaml.dump({"assumptions": {}}))
    scenario_path = scenarios_dir / "s.yaml"
    scenario_path.write_text(yaml.dump({"name": "s"}))

    settings = Settings(_env_file=None, seed_dir=seed_dir, raw_dir=tmp_path / "raw",
                         processed_dir=tmp_path / "processed" / "baseline")

    import pytest
    with pytest.raises(FileNotFoundError):
        main(scenario_path, settings)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/scenario/test_run.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.scenario.run'`

- [ ] **Step 3: Write `src/scenario/run.py`**

```python
import json
import logging
import sys

from src.config import Settings, settings as default_settings
from src.features.build import build_features
from src.model.run import resolve_backend
from src.models import Branch, BranchFeatures, Community, CommunityAssignment, Decision
from src.scenario.apply import apply_branch_overrides, apply_community_overrides
from src.scenario.baseline import load_baseline_assumptions
from src.scenario.diff import compute_branch_diff, compute_community_diff
from src.scenario.load import load_scenario
from src.scenario.models import ScenarioDiff

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main(scenario_path, settings: Settings | None = None) -> None:
    settings = settings or default_settings
    baseline_dir = settings.processed_dir
    current_dir = baseline_dir.parent / "current"
    raw_dir = settings.raw_dir
    scenarios_dir = settings.seed_dir.parent / "scenarios"

    if not (raw_dir / "branches.json").exists():
        raise FileNotFoundError(
            f"{raw_dir}/branches.json not found -- run `just all` to produce the baseline "
            "raw data before running a scenario."
        )
    if not (baseline_dir / "branch_features.json").exists():
        raise FileNotFoundError(
            f"{baseline_dir}/branch_features.json not found -- run `just all` to produce "
            "the baseline report before running a scenario."
        )

    baseline_assumptions = load_baseline_assumptions(scenarios_dir / "baseline.yaml")
    scenario = load_scenario(scenario_path)

    branches = [Branch(**b) for b in json.loads((raw_dir / "branches.json").read_text())]
    communities = [Community(**c) for c in json.loads((raw_dir / "communities.json").read_text())]
    price_flags = json.loads((raw_dir / "price_flags.json").read_text())

    branches = apply_branch_overrides(branches, scenario.overrides.branches)
    communities = apply_community_overrides(communities, scenario.overrides.communities)

    contest_ratio = (scenario.assumptions.contest_ratio
                      if scenario.assumptions.contest_ratio is not None
                      else baseline_assumptions.contest_ratio)
    model_backend = (scenario.assumptions.model_backend
                      if scenario.assumptions.model_backend is not None
                      else baseline_assumptions.model_backend)

    current_dir.mkdir(parents=True, exist_ok=True)
    current_settings = settings.model_copy(update={
        "processed_dir": current_dir,
        "contest_ratio": contest_ratio,
        "model_backend": model_backend,
    })

    features, network, assignments = build_features(branches, communities, price_flags,
                                                      contest_ratio)
    model = resolve_backend(current_settings)
    decisions = model.decide(features, network)

    (current_dir / "branch_features.json").write_text(json.dumps({
        "network": network.model_dump(),
        "branches": [f.model_dump() for f in features],
    }, indent=2))
    (current_dir / "community_assignment.json").write_text(
        json.dumps([a.model_dump() for a in assignments], indent=2))
    (current_dir / "communities.json").write_text(
        json.dumps([c.model_dump() for c in communities], indent=2))
    (current_dir / "decisions.json").write_text(
        json.dumps([d.model_dump() for d in decisions], indent=2))
    (current_dir / "run_meta.json").write_text(
        json.dumps({"model_backend": model.name, "scenario_name": scenario.name}, indent=2))

    baseline_payload = json.loads((baseline_dir / "branch_features.json").read_text())
    baseline_features = [BranchFeatures(**b) for b in baseline_payload["branches"]]
    baseline_decisions = [Decision(**d) for d in
                           json.loads((baseline_dir / "decisions.json").read_text())]
    baseline_assignments = [CommunityAssignment(**a) for a in
                             json.loads((baseline_dir / "community_assignment.json").read_text())]

    branch_diff = compute_branch_diff(baseline_features, baseline_decisions, features, decisions)
    community_diff = compute_community_diff(baseline_assignments, assignments)
    diff = ScenarioDiff(scenario_name=scenario.name, branches=branch_diff,
                         communities=community_diff)
    (current_dir / "diff.json").write_text(diff.model_dump_json(indent=2))

    changed_count = sum(1 for b in branch_diff if b.changed_fields or b.old is None)
    reassigned_count = sum(1 for c in community_diff if c.reassigned)
    print(f"scenario: '{scenario.name}' -> {len(features)} branches, {changed_count} changed, "
          f"{reassigned_count} communities reassigned. Wrote {current_dir}/diff.json")


if __name__ == "__main__":
    main(sys.argv[1])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/scenario/test_run.py -v`
Expected: 2 passed

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: 88 passed (86 + 2 new)

- [ ] **Step 6: Commit**

```bash
git add src/scenario/run.py tests/scenario/test_run.py
git commit -m "Add scenario run orchestrator: apply overrides, recompute, diff against baseline"
```

---

### Task 8: Example scenario file and real end-to-end validation

**Files:**
- Create: `data/scenarios/example-perturbations.yaml`
- Test: `tests/scenario/test_example_scenario.py`

**Interfaces:**
- Consumes: the real `data/seed/branches.csv` (9 real branches), `src.scenario.baseline.main`, `src.scenario.run.main`

- [ ] **Step 1: Write `data/scenarios/example-perturbations.yaml`**

Demonstrates the three requested perturbation types against real branch ids from
`data/seed/branches.csv`: a new hypothetical branch, a relocated existing branch,
and a rating change on an existing branch (which may or may not flip its
PROTECT/HOLD/SHRINK action -- the diff shows the real effect either way, not a
forced one).

```yaml
name: example-perturbations
assumptions:
  contest_ratio: 1.1
overrides:
  branches:
    # New hypothetical branch -- an id not in the seed data, so apply.py treats
    # it as a brand new entity rather than a patch. rating/review_count/
    # avg_price_aed are left out and default to null; source defaults to
    # "scenario" rather than "seed".
    dubai-marina-new:
      name: "Hypothetical Dubai Marina Branch"
      lat: 25.0805
      lng: 55.1403
      area: "Dubai Marina"

    # Relocate an existing real branch (al-safa-2) from its real coordinates
    # near Al Safa 2 to Deira's coordinates -- "what if this branch were in
    # Deira instead." Only lat/lng are patched; everything else about the
    # branch (name, rating, etc.) stays whatever baseline has.
    al-safa-2:
      lat: 25.2697
      lng: 55.3095

    # Rating change on an existing real branch (jumeirah-park), currently the
    # network's highest-rated branch at 4.8 -- "what if reviews got worse."
    jumeirah-park:
      rating: 3.9
```

- [ ] **Step 2: Write the failing test**

```python
# tests/scenario/test_example_scenario.py
import json

from src.config import REPO_ROOT, Settings
from src.scenario.baseline import main as baseline_main
from src.scenario.run import main as scenario_run_main


def test_example_scenario_runs_against_real_seed_data(tmp_path):
    # Real seed_dir/scenarios_dir (the project's actual data), but write raw/processed
    # output to tmp_path so this test doesn't touch the real data/raw or data/processed.
    raw_dir = tmp_path / "raw"
    baseline_dir = tmp_path / "processed" / "baseline"

    settings = Settings(_env_file=None, raw_dir=raw_dir, processed_dir=baseline_dir)
    baseline_main(settings)

    scenario_path = REPO_ROOT / "data" / "scenarios" / "example-perturbations.yaml"
    scenario_run_main(scenario_path, settings)

    current_dir = baseline_dir.parent / "current"
    features = json.loads((current_dir / "branch_features.json").read_text())
    branch_ids = {b["branch_id"] for b in features["branches"]}
    assert "dubai-marina-new" in branch_ids  # new branch present
    assert len(branch_ids) == 10  # 9 real branches + 1 new

    diff = json.loads((current_dir / "diff.json").read_text())
    by_id = {b["branch_id"]: b for b in diff["branches"]}

    assert by_id["dubai-marina-new"]["old"] is None
    assert by_id["dubai-marina-new"]["action_changed"] is True

    assert by_id["al-safa-2"]["changed_fields"]["lat"] == {"old": 25.1858, "new": 25.2697}
    assert by_id["al-safa-2"]["changed_fields"]["lng"] == {"old": 55.2410, "new": 55.3095}

    assert by_id["jumeirah-park"]["changed_fields"]["rating"] == {"old": 4.8, "new": 3.9}
    # action_changed may be True or False depending on where 3.9 lands in the rubric's
    # ranking -- both are valid outcomes, the point is changed_fields shows the real delta
    # regardless of whether it flipped the tier.

    community_diff = diff["communities"]
    assert len(community_diff) == 50  # all real communities present in the diff
```

- [ ] **Step 3: Run the test to verify it fails for the right reason first**

Run: `uv run pytest tests/scenario/test_example_scenario.py -v`
Expected: FAIL (the scenario YAML doesn't exist yet if Step 1 wasn't done, or assertions fail) -- confirm the failure is specifically about the missing/incomplete scenario file, not an import error, before moving on.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/scenario/test_example_scenario.py -v`
Expected: 1 passed. If `al-safa-2`'s baseline lat/lng values in the assertions don't match
`data/seed/branches.csv`'s actual values (25.1858, 55.2410) or `jumeirah-park`'s rating
doesn't match 4.8, re-check the real CSV (`cat data/seed/branches.csv`) and correct the
test's expected `"old"` values to match -- the CSV is the source of truth, not this plan.

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: 89 passed (88 + 1 new)

- [ ] **Step 6: Commit**

```bash
git add data/scenarios/example-perturbations.yaml tests/scenario/test_example_scenario.py
git commit -m "Add example scenario demonstrating new/relocated/re-rated branches"
```

---

### Task 9: Justfile wiring

**Files:**
- Modify: `justfile`

- [ ] **Step 1: Update `justfile`**

```makefile
# Stages 1-3: acquire -> features -> model, using data/scenarios/baseline.yaml's
# assumptions. Writes data/raw/*.json and data/processed/baseline/*.json.
all:
    uv run python -m src.scenario.baseline

# Serve the JSON API + Leaflet frontend on http://localhost:8000
serve:
    uv run uvicorn src.serve.app:app --reload --port 8000

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
```

- [ ] **Step 2: Verify the full pipeline + a scenario run end to end**

```bash
unset ANTHROPIC_API_KEY
just clean && just all
just scenario data/scenarios/example-perturbations.yaml
```

Expected: `just all` prints the acquire/features/model summaries as before (now
reading `data/scenarios/baseline.yaml`'s assumptions) and writes into
`data/processed/baseline/`. `just scenario ...` prints a line like
`scenario: 'example-perturbations' -> 10 branches, N changed, M communities
reassigned. Wrote .../data/processed/current/diff.json` and creates
`data/processed/current/diff.json`.

- [ ] **Step 3: Run the full test suite once more**

Run: `just test`
Expected: 89 passed.

- [ ] **Step 4: Commit**

```bash
git add justfile
git commit -m "Wire justfile: all uses baseline.yaml, add scenario recipe"
```

---

### Task 10: `/api/diff` endpoint

**Files:**
- Modify: `src/serve/app.py`
- Modify: `tests/serve/test_app.py`

**Interfaces:**
- Produces: `GET /api/diff` returning `{"available": false}` or `{"available": true, "scenario_name": ..., "branches": [...], "communities": [...]}`.

- [ ] **Step 1: Update the existing `client` fixture and manual-Settings tests in `tests/serve/test_app.py` to nest under `baseline/`**

Change the `client` fixture's `processed_dir` construction from:
```python
@pytest.fixture
def client(tmp_path):
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
```
to:
```python
@pytest.fixture
def client(tmp_path):
    processed_dir = tmp_path / "processed" / "baseline"
    processed_dir.mkdir(parents=True)
```

Apply the same change (`tmp_path / "processed" / "baseline"` + `mkdir(parents=True)`)
to the two manually-constructed-`Settings` tests:
`test_network_reports_actual_backend_from_run_meta_not_configured_setting` and
`test_network_falls_back_to_configured_backend_when_run_meta_absent`. No other
assertions in those tests need to change -- they still read/write files relative
to whatever `processed_dir` is, just now a nested path.

- [ ] **Step 2: Write the failing tests for `/api/diff`**

Add to `tests/serve/test_app.py`:

```python
async def test_diff_unavailable_when_no_scenario_has_run(client):
    async with client as c:
        resp = await c.get("/api/diff")
    assert resp.json() == {"available": False}


async def test_diff_returns_scenario_diff_when_present(tmp_path):
    processed_dir = tmp_path / "processed" / "baseline"
    processed_dir.mkdir(parents=True)
    _seed_processed(processed_dir)

    current_dir = tmp_path / "processed" / "current"
    current_dir.mkdir(parents=True)
    (current_dir / "diff.json").write_text(json.dumps({
        "scenario_name": "example-perturbations",
        "branches": [{
            "branch_id": "a", "old": {"action": "PROTECT"}, "new": {"action": "HOLD"},
            "changed_fields": {"rating": {"old": 4.5, "new": 3.9}}, "action_changed": True,
        }],
        "communities": [{
            "community_id": "c1", "reassigned": False,
            "old_branch_id": "a", "new_branch_id": "a",
        }],
    }))

    settings = Settings(_env_file=None, processed_dir=processed_dir, model_backend="rubric")
    app = create_app(settings)
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")

    async with client as c:
        resp = await c.get("/api/diff")
    body = resp.json()

    assert body["available"] is True
    assert body["scenario_name"] == "example-perturbations"
    assert body["branches"][0]["action_changed"] is True
    assert body["communities"][0]["reassigned"] is False
```

- [ ] **Step 3: Run the new tests to verify they fail**

Run: `uv run pytest tests/serve/test_app.py -v`
Expected: the fixture-updated existing tests still pass; the two new `/api/diff`
tests FAIL with a 404 (route doesn't exist yet).

- [ ] **Step 4: Add the `/api/diff` route to `src/serve/app.py`**

Add this route inside `create_app`, after the existing `/api/network` route and
before `return app`:

```python
    @app.get("/api/diff")
    def diff():
        current_dir = settings.processed_dir.parent / "current"
        diff_path = current_dir / "diff.json"
        if not diff_path.exists():
            return {"available": False}
        payload = json.loads(diff_path.read_text())
        return {"available": True, **payload}
```

- [ ] **Step 5: Run all of `tests/serve/test_app.py`**

Run: `uv run pytest tests/serve/test_app.py -v`
Expected: all pass (9 tests: 7 pre-existing + 2 new).

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest -q`
Expected: 91 passed (89 + 2 new).

- [ ] **Step 7: Commit**

```bash
git add src/serve/app.py tests/serve/test_app.py
git commit -m "Add /api/diff endpoint; nest test fixtures under processed/baseline"
```

---

### Task 11: Frontend diff mode

**Files:**
- Modify: `src/serve/static/index.html`
- Modify: `src/serve/static/app.js`
- Modify: `src/serve/static/style.css`

**Interfaces:**
- Consumes: `GET /api/diff`
- Produces: a diff-mode toggle that highlights changed branches/communities on the map and shows old->new deltas in the side panel. No automated tests (matches v0's "no tests beyond smoke tests" principle for the frontend) -- verified manually per Step 6. Every dynamic value touching `innerHTML` goes through `escapeHtml()` — the new diff section specifically routes through a dedicated `formatChangedFieldRow()` helper (Step 5) so every field/old/new value is escaped before it reaches the template string, exactly like the existing `fmt()` helper already does for the rest of the side panel.

- [ ] **Step 1: Add the diff toggle to `src/serve/static/index.html`**

In the `#layer-toggles` div, add a third label after the existing two:
```html
    <div id="layer-toggles">
      <label><input type="checkbox" id="toggle-communities" checked /> Communities</label>
      <label><input type="checkbox" id="toggle-assignment-lines" /> Assignment lines</label>
      <label><input type="checkbox" id="toggle-diff" disabled /> Diff vs baseline</label>
    </div>
```

- [ ] **Step 2: Add diff styling to `src/serve/static/style.css`**

Add at the end of the file:
```css
.diff-section { margin-top: 0.75rem; padding-top: 0.5rem; border-top: 1px solid #ccc; }
.diff-section table { width: 100%; }
.diff-old { color: #c62828; text-decoration: line-through; }
.diff-new { color: #2e7d32; font-weight: bold; }
```

- [ ] **Step 3: Fetch diff data and enable the toggle in `src/serve/static/app.js`'s `main()`**

Change the top-level `let` declarations (after the existing `let siblingLineLayer = L.layerGroup();` line) to add:
```javascript
let diffData = null;
let diffHighlightLayer = L.layerGroup();
```

Change `main()`'s fetch block from:
```javascript
    const [branchResp, communityResp, networkPayload] = await Promise.all([
      fetchJson("/api/branches"), fetchJson("/api/communities"), fetchJson("/api/network"),
    ]);
    branches = branchResp;
    communities = communityResp;
    network = networkPayload.stats;
```
to:
```javascript
    const [branchResp, communityResp, networkPayload, diffPayload] = await Promise.all([
      fetchJson("/api/branches"), fetchJson("/api/communities"), fetchJson("/api/network"),
      fetchJson("/api/diff"),
    ]);
    branches = branchResp;
    communities = communityResp;
    network = networkPayload.stats;
    if (diffPayload.available) {
      diffData = diffPayload;
    }
```

After the existing `document.getElementById("assumptions-toggle").addEventListener(...)` block
(still inside the `try`, before the closing `}` of the try block), add:
```javascript
    if (diffData) {
      renderDiffHighlights();
      document.getElementById("toggle-diff").disabled = false;
      document.getElementById("toggle-diff").addEventListener("change", (e) => {
        if (e.target.checked) diffHighlightLayer.addTo(map); else map.removeLayer(diffHighlightLayer);
      });
    }
```

- [ ] **Step 4: Add `renderDiffHighlights()` to `src/serve/static/app.js`**

Add this new function after `renderCommunities()` and before `showLoadError()`:

```javascript
function diffEntryFor(branchId) {
  if (!diffData) return null;
  return diffData.branches.find(d => d.branch_id === branchId) || null;
}

function renderDiffHighlights() {
  const branchById = Object.fromEntries(branches.map(b => [b.branch_id, b]));
  const communityById = Object.fromEntries(communities.map(c => [c.community_id, c]));

  for (const entry of diffData.branches) {
    if (entry.old === null && entry.new !== null) {
      // New branch introduced by the scenario -- not in /api/branches at all.
      const marker = L.circleMarker([entry.new.lat, entry.new.lng], {
        radius: popRadius(entry.new.female_pop_served || 0),
        color: ACTION_COLORS[entry.new.action] || "#999",
        fillColor: ACTION_COLORS[entry.new.action] || "#999",
        fillOpacity: 0.5,
        dashArray: "4 4",
        weight: 2,
      });
      marker.bindTooltip(`${escapeHtml(shortBranchName(entry.new.name))} (new, ${escapeHtml(entry.new.action)})`,
        { permanent: true, direction: "top" });
      marker.on("click", () => renderSidePanel(entry.new, entry));
      diffHighlightLayer.addLayer(marker);
    } else if (entry.action_changed || Object.keys(entry.changed_fields).length > 0) {
      const branch = branchById[entry.branch_id];
      if (!branch) continue;
      const ring = L.circleMarker([branch.lat, branch.lng], {
        radius: popRadius(branch.female_pop_served) + 5,
        color: "#000", weight: 2, dashArray: "2 4", fill: false,
      });
      diffHighlightLayer.addLayer(ring);
    }
  }

  for (const entry of diffData.communities) {
    if (!entry.reassigned) continue;
    const community = communityById[entry.community_id];
    if (!community) continue;
    const ring = L.circleMarker([community.lat ?? 0, community.lng ?? 0], {
      radius: 7, color: "#000", weight: 2, dashArray: "2 4", fill: false,
    });
    diffHighlightLayer.addLayer(ring);
  }
}
```

- [ ] **Step 5: Add an escaped row-formatting helper and augment `renderSidePanel()` to show old->new deltas**

Add this helper function near `fmt()` (immediately after it):

```javascript
function formatChangedFieldRow(field, delta) {
  const label = escapeHtml(field);
  const oldValue = escapeHtml(delta.old);
  const newValue = escapeHtml(delta.new);
  return `<tr><td>${label}</td><td><span class="diff-old">${oldValue}</span> &rarr; <span class="diff-new">${newValue}</span></td></tr>`;
}

function renderDiffSection(diffEntry) {
  if (!diffEntry) return "";
  const hasChanges = diffEntry.action_changed || Object.keys(diffEntry.changed_fields).length > 0;
  if (!hasChanges) return "";
  const rowsHtml = diffEntry.old === null
    ? '<tr><td colspan="2">New in this scenario</td></tr>'
    : Object.entries(diffEntry.changed_fields).map(([field, delta]) => formatChangedFieldRow(field, delta)).join("");
  return `
    <div class="diff-section">
      <h4>Changed since baseline</h4>
      <table>${rowsHtml}</table>
    </div>
  `;
}
```

Change `renderSidePanel`'s signature from:
```javascript
function renderSidePanel(branch) {
```
to:
```javascript
function renderSidePanel(branch, diffEntry) {
  diffEntry = diffEntry || diffEntryFor(branch.branch_id);
```

In `renderBranches()`, change:
```javascript
    marker.on("click", () => {
      renderSidePanel(branch);
      drawSiblingLinks(branch);
      siblingLineLayer.addTo(map);
    });
```
to:
```javascript
    marker.on("click", () => {
      renderSidePanel(branch, diffEntryFor(branch.branch_id));
      drawSiblingLinks(branch);
      siblingLineLayer.addTo(map);
    });
```

In `renderSidePanel`'s `panel.innerHTML = \`...\`` template string, immediately after the
existing `<p><strong>Caveats:</strong> ...</p>` line and before the closing backtick, add
one interpolation calling the new helper (every value it touches is already escaped inside
`renderDiffSection`/`formatChangedFieldRow`, so this line only ever inserts pre-escaped
HTML or a static empty string):
```javascript
    ${renderDiffSection(diffEntry)}
```

- [ ] **Step 6: Run the real pipeline, run the example scenario, and verify manually**

```bash
cd /home/aditya/github.com/thenomadlad/2pz-ai-case-study
unset ANTHROPIC_API_KEY
just clean && just all
just scenario data/scenarios/example-perturbations.yaml
uv run uvicorn src.serve.app:app --port 8000 &
sleep 1
curl -s http://localhost:8000/api/diff | head -c 500
```

Then use a browser automation tool (Playwright, if available) to navigate to
`http://localhost:8000` and confirm: the "Diff vs baseline" checkbox is enabled
(not greyed out), toggling it on shows a new dashed marker near Dubai Marina
(the hypothetical branch), a dashed ring appears over `al-safa-2`'s baseline
position (the branch's own marker from `/api/branches` still renders at its
baseline location since that endpoint is baseline-only -- the dashed ring is
the "something changed here" signal; clicking it shows the branch's baseline
data plus a "Changed since baseline" section with the old->new lat/lng),
clicking the new dashed Dubai Marina marker opens the side panel showing "New
in this scenario", and clicking `jumeirah-park` shows a "Changed since
baseline" section with `rating: 4.8 -> 3.9`. Take a screenshot if possible.
Stop the server when done (`kill %1`).

- [ ] **Step 7: Commit**

```bash
git add src/serve/static/index.html src/serve/static/app.js src/serve/static/style.css
git commit -m "Add diff-mode frontend: highlight changed branches/communities, side panel deltas"
```

---

### Task 12: README updates

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a scenario-usage section to `README.md`**

After the existing "Flip the decision backend" section, add:

```markdown
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
```

- [ ] **Step 2: Run the full suite one final time for this task (no code changed, just confirming nothing else broke)**

Run: `uv run pytest -q`
Expected: 91 passed.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Document the v1 perturbation workflow in README"
```

---

### Task 13: Final end-to-end verification

**Files:** None (verification only).

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -v`
Expected: 91 passed, 0 failures.

- [ ] **Step 2: Run the complete documented workflow from a clean state**

```bash
cd /home/aditya/github.com/thenomadlad/2pz-ai-case-study
unset ANTHROPIC_API_KEY
just clean
just all
just scenario data/scenarios/example-perturbations.yaml
```

Expected: `just all` prints acquire (9 branches, 50 communities), features, and model
(falls back to rubric, no API key) summaries, writing into `data/processed/baseline/`.
`just scenario ...` prints a one-line summary naming how many branches changed and how
many communities were reassigned, and `data/processed/current/diff.json` exists and is
valid JSON.

- [ ] **Step 3: Verify `data/processed/baseline/` was untouched by the scenario run**

```bash
stat -c '%Y' data/processed/baseline/decisions.json
just scenario data/scenarios/example-perturbations.yaml
stat -c '%Y' data/processed/baseline/decisions.json
```

Expected: the two `stat` timestamps for `data/processed/baseline/decisions.json` are
identical -- running a scenario must not modify anything under `baseline/`.

- [ ] **Step 4: Start the server and verify the diff is served**

```bash
uv run uvicorn src.serve.app:app --port 8000 &
sleep 1
curl -s http://localhost:8000/api/diff | python3 -c "import json,sys; d=json.load(sys.stdin); print('available:', d['available']); print('scenario:', d.get('scenario_name')); print('branches in diff:', len(d.get('branches', [])))"
kill %1
```

Expected: `available: True`, `scenario: example-perturbations`, `branches in diff: 10`.

- [ ] **Step 5: Confirm no regressions in the v0 done-state check**

```bash
uv run uvicorn src.serve.app:app --port 8000 &
sleep 1
curl -s http://localhost:8000/api/branches | python3 -c "import json,sys; print(len(json.load(sys.stdin)))"
curl -s http://localhost:8000/api/network | python3 -c "import json,sys; print(json.load(sys.stdin)['model_backend'])"
kill %1
```

Expected: `9` (real branches from baseline) and `rubric` (correct fallback, matching v0's
original zero-API-key guarantee -- still holds in v1).

- [ ] **Step 6: Report final status**

No commit for this task (verification only) unless Step 2-5 surfaced a fix, in which case
make the fix, re-run the affected steps, and commit the fix with a clear message naming
which verification step caught it.

---

## Self-Review Notes

- **Spec coverage:** `docs/designs/v1.md`'s architecture section maps directly:
  baseline (Tasks 3, 9) -> scenario domain models (Task 2) -> scenario loader (Task 4) ->
  override application incl. patch-vs-new (Task 5) -> diff (Task 6) -> orchestrator (Task 7)
  -> example scenario (Task 8) -> API (Task 10) -> frontend (Task 11). "Why acquire isn't
  re-run" is enforced structurally: `ScenarioAssumptions` (Task 2) simply has no
  `global_female_share`/`fallback_price_aed` fields, so there's no field to misuse. The
  "baseline stays reality, no promote" constraint is enforced by `scenario/run.py` never
  writing anywhere under `baseline_dir` (Task 7) -- verified explicitly in Task 13 Step 3.
- **Placeholder scan:** no TBD/TODO. Task 13's "make a fix if verification surfaces one" is
  a standard final-task allowance, not a placeholder for undesigned work -- every prior task
  is independently complete and tested.
- **Type consistency:** `build_features` returns `(features, network, assignments)` (the
  3-tuple from v0's post-review fix) used consistently in Task 7. `Scenario.overrides` is a
  `ScenarioOverrides` object (`.branches`/`.communities` attribute access), not a raw dict --
  Task 7's `scenario.overrides.branches` matches Task 2's model definition exactly.
  `BranchDiffEntry.old`/`.new` are `dict[str, Any] | None`, matching both Task 6's
  `compute_branch_diff` construction and Task 11's frontend consumption (`entry.new.lat`,
  etc., read as plain JS object properties off the JSON-serialized dict).
- **Security:** Task 11's diff-section rendering routes every interpolated value through
  `formatChangedFieldRow()` -> `escapeHtml()`, matching the existing `fmt()` pattern already
  used by the rest of `renderSidePanel`. No new unescaped `innerHTML` sink is introduced.
