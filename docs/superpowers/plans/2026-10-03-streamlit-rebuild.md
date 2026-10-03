# Streamlit Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the FastAPI/Leaflet/Netlify demo with a native Streamlit app that supports live perturbation (no frozen JSON snapshot) and is structured pyramid-principle-first for a consulting audience: Product → Model/Assumptions/Data → Story.

**Architecture:** Streamlit imports `src.acquire`/`src.features`/`src.model`/`src.scenario` directly, in-process — no HTTP layer. A new `src/webapp/` package holds the Streamlit-specific orchestration (data loading, pydeck map layers, the widget-based scenario editor, and the three page modules), wired together by a root `streamlit_app.py` using `st.navigation`/`st.Page`. One existing module gets a real refactor (`src/scenario/run.py`, to expose an in-memory `run_scenario()`); everything else under `src/acquire`, `src/features`, `src/model`, `src/scenario/{apply,baseline,diff,load,models}.py`, and `src/models.py` is untouched.

**Tech Stack:** Python 3.11+, `uv`, Streamlit (native `st.pydeck_chart`, no added map library), `pydantic`, `pyyaml`. Dropped: `fastapi`, `uvicorn`, `httpx`.

**Full design reference:** `docs/superpowers/specs/2026-10-03-streamlit-rebuild-design.md` — read it before Task 1 if anything below is ambiguous; this plan implements it task-by-task but doesn't repeat its rationale.

## Global Constraints

- **Deleted, not deprecated:** `src/serve/`, `scripts/build_static_demo.py`, `static-site/`, `netlify.toml`, `.netlify/`, `tests/serve/`. `fastapi`, `uvicorn[standard]`, `httpx` removed from `pyproject.toml` — confirmed nothing else imports them.
- **Untouched:** `src/acquire/`, `src/features/`, `src/model/`, `src/models.py`, `src/scenario/apply.py`, `src/scenario/baseline.py`, `src/scenario/diff.py`, `src/scenario/load.py`, `src/scenario/models.py` (only *additive* — a new `ScenarioRun` model is added there, nothing existing in it changes).
- **Map:** `st.pydeck_chart` only. No `streamlit-folium`, no `folium`, no Mapbox token.
- **Page order is Product → Model → Story**, enforced by the literal order of the list passed to `st.navigation()` in `streamlit_app.py` — not by file naming.
- **Scenario runs are in-memory.** `run_scenario(scenario, settings) -> ScenarioRun` never writes its own scenario-output artifacts (features/decisions/diff) to disk; only the CLI wrapper (`main()` in `src/scenario/run.py`) writes `data/processed/current/*`. (The LLM backend's own response cache under `.llm_cache/`, if that backend is selected, is a separate, pre-existing, namespaced side effect of `src/model/llm.py` — untouched by this plan and not a violation of this constraint.) The Streamlit app calls `run_scenario()` directly and holds the result in `st.session_state`; the widget-based scenario editor (Task 5) defaults to the rubric backend specifically so the live perturbation loop never depends on that cache.
- **Rubric is the default backend** for every scenario built through the widget editor (matches `docs/designs/v1.md`'s own recommendation — the LLM cache never helps across different scenarios).
- **Secrets:** `ANTHROPIC_API_KEY` flows through `.streamlit/secrets.toml` (gitignored) locally and Streamlit Community Cloud's Secrets panel in production. Streamlit mirrors top-level secrets into `os.environ`, so `src/config.py`'s `Settings` (pydantic-settings) needs **zero code changes** to pick it up. Do not add an `st.secrets` fallback branch anywhere — if `ANTHROPIC_API_KEY` isn't visible via `os.environ` in a deployed app, that's a secrets-panel configuration problem, not a code problem to work around.
- **Testing:** pytest for everything under `src/`; `streamlit.testing.v1.AppTest` for page-level smoke tests under `tests/webapp/`. No test should start a live Streamlit server.

---

### Task 1: Extract `run_scenario()` from `src/scenario/run.py`

**Files:**
- Modify: `src/scenario/run.py`
- Modify: `src/scenario/models.py`
- Modify: `tests/scenario/test_run.py`

**Interfaces:**
- Produces: `run_scenario(scenario: Scenario, settings: Settings | None = None) -> ScenarioRun` — the function every later task (webapp's scenario editor, page 1) calls directly. No disk I/O. Raises `FileNotFoundError` under the same conditions `main()` does today (missing `data/raw/branches.json` or missing baseline `branch_features.json`).
- Produces: `ScenarioRun` pydantic model in `src/scenario/models.py`: fields `scenario_name: str`, `features: list[BranchFeatures]`, `network: NetworkStats`, `assignments: list[CommunityAssignment]`, `communities: list[Community]`, `decisions: list[Decision]`, `diff: ScenarioDiff`.
- Consumes (unchanged): `apply_branch_overrides`, `apply_community_overrides` (`src/scenario/apply.py`), `load_baseline_assumptions` (`src/scenario/baseline.py`), `load_scenario` (`src/scenario/load.py`), `compute_branch_diff`, `compute_community_diff` (`src/scenario/diff.py`), `build_features` (`src/features/build.py`), `resolve_backend` (`src/model/run.py`).

This is a pure refactor — every existing test in `tests/scenario/test_run.py` must keep passing unchanged (they test `main()`, which keeps its exact file-writing behavior). The new tests below test `run_scenario()` directly.

- [ ] **Step 1: Add `ScenarioRun` to `src/scenario/models.py`**

Add at the end of the file:

```python
class ScenarioRun(BaseModel):
    scenario_name: str
    features: list[BranchFeatures]
    network: NetworkStats
    assignments: list[CommunityAssignment]
    communities: list[Community]
    decisions: list[Decision]
    diff: ScenarioDiff
```

And add the needed imports at the top of `src/scenario/models.py`:

```python
from src.models import BranchFeatures, Community, CommunityAssignment, Decision, NetworkStats
```

- [ ] **Step 2: Write the failing tests for `run_scenario()`**

Add to `tests/scenario/test_run.py` (it already imports `main`; add this import alongside it):

```python
from src.scenario.run import main, run_scenario
```

Add these test functions, reusing the existing `_write_seed_and_baseline` helper already in the file:

```python
def test_run_scenario_returns_bundle_without_touching_disk(tmp_path):
    seed_dir, raw_dir, baseline_dir, scenarios_dir = _write_seed_and_baseline(tmp_path)

    scenario_path = scenarios_dir / "test-scenario.yaml"
    scenario_path.write_text(yaml.dump({
        "name": "test-scenario",
        "assumptions": {"model_backend": "rubric"},
        "overrides": {"branches": {"a": {"rating": 3.0}}},
    }))

    from src.scenario.load import load_scenario
    scenario = load_scenario(scenario_path)
    settings = Settings(_env_file=None, seed_dir=seed_dir, raw_dir=raw_dir,
                         processed_dir=baseline_dir)

    current_dir = baseline_dir.parent / "current"
    assert not current_dir.exists()

    run = run_scenario(scenario, settings)

    assert not current_dir.exists()  # no disk writes from run_scenario itself
    assert run.scenario_name == "test-scenario"
    assert len(run.features) == 2  # a, b
    by_id = {d.branch_id: d for d in run.decisions}
    assert "a" in by_id and "b" in by_id
    diff_by_id = {b.branch_id: b for b in run.diff.branches}
    assert diff_by_id["a"].changed_fields["rating"] == {"old": 4.5, "new": 3.0}


def test_main_writes_identical_output_via_run_scenario(tmp_path):
    # main() must still write byte-for-byte the same four files + diff.json it always has --
    # this is the regression guard that the refactor didn't change CLI behavior.
    seed_dir, raw_dir, baseline_dir, scenarios_dir = _write_seed_and_baseline(tmp_path)

    scenario_path = scenarios_dir / "test-scenario.yaml"
    scenario_path.write_text(yaml.dump({
        "name": "test-scenario",
        "assumptions": {"model_backend": "rubric"},
        "overrides": {"branches": {"a": {"rating": 3.0}}},
    }))

    settings = Settings(_env_file=None, seed_dir=seed_dir, raw_dir=raw_dir,
                         processed_dir=baseline_dir)
    main(scenario_path, settings)

    current_dir = baseline_dir.parent / "current"
    for name in ("branch_features.json", "community_assignment.json", "communities.json",
                 "decisions.json", "run_meta.json", "diff.json"):
        assert (current_dir / name).exists()
```

- [ ] **Step 3: Run the new tests to verify they fail**

Run: `uv run pytest tests/scenario/test_run.py -v`
Expected: `test_run_scenario_returns_bundle_without_touching_disk` and
`test_main_writes_identical_output_via_run_scenario` FAIL with
`ImportError: cannot import name 'run_scenario'`.

- [ ] **Step 4: Rewrite `src/scenario/run.py`**

Replace the full contents of `src/scenario/run.py` with:

```python
import json
import logging

from src.config import Settings, settings as default_settings
from src.features.build import build_features
from src.model.run import resolve_backend
from src.models import Branch, BranchFeatures, Community, CommunityAssignment, Decision
from src.scenario.apply import apply_branch_overrides, apply_community_overrides
from src.scenario.baseline import load_baseline_assumptions
from src.scenario.diff import compute_branch_diff, compute_community_diff
from src.scenario.load import load_scenario
from src.scenario.models import Scenario, ScenarioDiff, ScenarioRun

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def run_scenario(scenario: Scenario, settings: Settings | None = None) -> ScenarioRun:
    """Apply a scenario's overrides on top of the fixed baseline raw data, recompute
    features+model, and diff against the baseline report -- entirely in memory. Never
    writes to disk; callers that need the on-disk artifacts (the CLI) do that themselves
    with the returned bundle.
    """
    settings = settings or default_settings
    baseline_dir = settings.processed_dir
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

    raw_branches = [Branch(**b) for b in json.loads((raw_dir / "branches.json").read_text())]
    communities = [Community(**c) for c in json.loads((raw_dir / "communities.json").read_text())]
    price_flags = json.loads((raw_dir / "price_flags.json").read_text())

    original_branch_ids = {b.id for b in raw_branches}
    branches = apply_branch_overrides(raw_branches, scenario.overrides.branches)
    communities = apply_community_overrides(communities, scenario.overrides.communities)

    # A scenario-introduced new branch with no avg_price_aed given gets the network median
    # imputed by build_features just like any branch with a missing price -- but its id was
    # never in price_flags (that only comes from the ACQUIRE stage, which never runs for a
    # new scenario entity), so estimated_fields wouldn't flag it. Add those ids explicitly
    # so the imputed price is honestly flagged, not shown as if it were reported.
    new_unpriced_ids = [b.id for b in branches
                         if b.id not in original_branch_ids and b.avg_price_aed is None]
    price_flags = [*price_flags, *new_unpriced_ids]

    contest_ratio = (scenario.assumptions.contest_ratio
                      if scenario.assumptions.contest_ratio is not None
                      else baseline_assumptions.contest_ratio)
    model_backend = (scenario.assumptions.model_backend
                      if scenario.assumptions.model_backend is not None
                      else baseline_assumptions.model_backend)

    # Redirect processed_dir (not an on-disk write by itself) so that IF the llm backend is
    # used, its disk cache lands under data/processed/current/.llm_cache -- never inside
    # baseline/, which must never be touched by a scenario run (LLMModel creates this
    # directory itself on construction; run_scenario never creates it).
    current_dir = baseline_dir.parent / "current"
    current_settings = settings.model_copy(update={
        "processed_dir": current_dir,
        "contest_ratio": contest_ratio,
        "model_backend": model_backend,
    })

    features, network, assignments = build_features(branches, communities, price_flags,
                                                      contest_ratio)
    model = resolve_backend(current_settings)
    decisions = model.decide(features, network)

    baseline_payload = json.loads((baseline_dir / "branch_features.json").read_text())
    baseline_features = [BranchFeatures(**b) for b in baseline_payload["branches"]]
    baseline_decisions = [Decision(**d) for d in
                           json.loads((baseline_dir / "decisions.json").read_text())]
    baseline_assignments = [CommunityAssignment(**a) for a in
                             json.loads((baseline_dir / "community_assignment.json").read_text())]

    # Records which backend produced each side of the diff, the same way the old /api/network
    # read it, so a flip can be attributed to "inputs changed" vs. "decision method changed".
    baseline_run_meta_path = baseline_dir / "run_meta.json"
    if baseline_run_meta_path.exists():
        baseline_backend = json.loads(baseline_run_meta_path.read_text())["model_backend"]
    else:
        baseline_backend = settings.model_backend

    branch_diff = compute_branch_diff(baseline_features, baseline_decisions, features, decisions)
    community_diff = compute_community_diff(baseline_assignments, assignments)
    diff = ScenarioDiff(scenario_name=scenario.name, branches=branch_diff,
                         communities=community_diff,
                         baseline_backend=baseline_backend, current_backend=model.name)

    return ScenarioRun(scenario_name=scenario.name, features=features, network=network,
                        assignments=assignments, communities=communities, decisions=decisions,
                        diff=diff)


def main(scenario_path, settings: Settings | None = None) -> None:
    settings = settings or default_settings
    scenario = load_scenario(scenario_path)
    run = run_scenario(scenario, settings)

    current_dir = settings.processed_dir.parent / "current"
    current_dir.mkdir(parents=True, exist_ok=True)

    (current_dir / "branch_features.json").write_text(json.dumps({
        "network": run.network.model_dump(),
        "branches": [f.model_dump() for f in run.features],
    }, indent=2))
    (current_dir / "community_assignment.json").write_text(
        json.dumps([a.model_dump() for a in run.assignments], indent=2))
    (current_dir / "communities.json").write_text(
        json.dumps([c.model_dump() for c in run.communities], indent=2))
    (current_dir / "decisions.json").write_text(
        json.dumps([d.model_dump() for d in run.decisions], indent=2))
    (current_dir / "run_meta.json").write_text(
        json.dumps({"model_backend": run.diff.current_backend,
                     "scenario_name": run.scenario_name}, indent=2))
    (current_dir / "diff.json").write_text(run.diff.model_dump_json(indent=2))

    changed_count = sum(1 for b in run.diff.branches if b.changed_fields or b.old is None)
    reassigned_count = sum(1 for c in run.diff.communities if c.reassigned)
    print(f"scenario: '{run.scenario_name}' -> {len(run.features)} branches, {changed_count} "
          f"changed, {reassigned_count} communities reassigned. Wrote {current_dir}/diff.json")


if __name__ == "__main__":
    import sys
    main(sys.argv[1])
```

- [ ] **Step 5: Run all scenario tests to verify they pass**

Run: `uv run pytest tests/scenario/ -v`
Expected: all pass, including every pre-existing test in `test_run.py` (byte-for-byte
unchanged behavior) and the two new ones from Step 2.

- [ ] **Step 6: Commit**

```bash
git add src/scenario/run.py src/scenario/models.py tests/scenario/test_run.py
git commit -m "Extract in-memory run_scenario() from scenario CLI main()"
```

---

### Task 2: Delete the FastAPI/Leaflet/Netlify stack

**Files:**
- Delete: `src/serve/` (entire directory), `scripts/build_static_demo.py`, `static-site/` (entire directory), `netlify.toml`, `.netlify/` (entire directory), `tests/serve/` (entire directory)
- Modify: `pyproject.toml`
- Modify: `justfile`

**Interfaces:** None — this task only removes things. Nothing later depends on anything deleted here (confirmed: `httpx`/`fastapi` are not imported anywhere outside the deleted set).

- [ ] **Step 1: Delete the files**

```bash
git rm -r src/serve scripts/build_static_demo.py static-site netlify.toml tests/serve
rm -rf .netlify
```

- [ ] **Step 2: Remove the now-unused dependencies from `pyproject.toml`**

In the `dependencies` list, remove these three lines:
```
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "httpx>=0.27",
```

- [ ] **Step 3: Update the justfile's `serve` recipe**

Replace:
```
# Serve the JSON API + Leaflet frontend on http://localhost:8000
serve:
    uv run uvicorn src.serve.app:app --reload --port 8000
```

with:
```
# Launch the Streamlit app on http://localhost:8501
app:
    uv run streamlit run streamlit_app.py
```

(`streamlit_app.py` doesn't exist until Task 6 — that's expected; this recipe isn't
runnable until then, same as any multi-task build.)

- [ ] **Step 4: Regenerate the lockfile and run the full test suite**

Run: `uv sync --extra dev && uv run pytest`
Expected: all pass (the deleted `tests/serve/` tests are gone, nothing else referenced
`src/serve`).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "Delete FastAPI/Leaflet/Netlify stack, replaced by Streamlit"
```

---

### Task 3: `src/webapp/data.py` — baseline loader

**Files:**
- Create: `src/webapp/__init__.py` (empty)
- Create: `src/webapp/data.py`
- Create: `tests/webapp/__init__.py` (empty)
- Create: `tests/webapp/test_data.py`

**Interfaces:**
- Produces: `BaselineData` dataclass and `load_baseline(settings: Settings | None = None) -> BaselineData`, consumed by Task 7 (page 1) and Task 8 (page 2).
  - `BaselineData` fields: `features: list[BranchFeatures]`, `decisions: list[Decision]`, `assignments: list[CommunityAssignment]`, `communities: list[Community]`, `network: NetworkStats`, `model_backend: str`, `data_sources: dict[str, str]`, `pipeline_run_at: datetime.datetime`.
  - Method `decision_for(branch_id: str) -> Decision | None`.
  - Method `communities_by_id() -> dict[str, Community]`.

This replaces the per-route `_load`/join logic that used to live in `src/serve/app.py` — same joins, same "report actual backend from `run_meta.json`, fall back to configured setting" behavior, just as plain functions instead of FastAPI routes.

- [ ] **Step 1: Write the failing tests**

Create `tests/webapp/test_data.py`:

```python
import json

from src.config import Settings
from src.webapp.data import load_baseline


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


def test_load_baseline_joins_and_reports_actual_backend(tmp_path):
    processed_dir = tmp_path / "processed" / "baseline"
    processed_dir.mkdir(parents=True)
    _seed_processed(processed_dir)
    (processed_dir / "run_meta.json").write_text(json.dumps({"model_backend": "rubric"}))

    settings = Settings(_env_file=None, processed_dir=processed_dir, model_backend="llm",
                         anthropic_api_key=None)
    data = load_baseline(settings)

    assert data.network.branch_count == 1
    assert data.model_backend == "rubric"  # from run_meta.json, not the configured "llm"
    assert data.decision_for("a").action == "PROTECT"
    assert data.decision_for("missing") is None
    assert data.communities_by_id()["c1"].name_en == "C1"


def test_load_baseline_falls_back_to_configured_backend_when_run_meta_absent(tmp_path):
    processed_dir = tmp_path / "processed" / "baseline"
    processed_dir.mkdir(parents=True)
    _seed_processed(processed_dir)
    assert not (processed_dir / "run_meta.json").exists()

    settings = Settings(_env_file=None, processed_dir=processed_dir, model_backend="rubric")
    data = load_baseline(settings)

    assert data.model_backend == "rubric"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/webapp/test_data.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.webapp'`.

- [ ] **Step 3: Create `src/webapp/__init__.py` and `tests/webapp/__init__.py`**

Both empty files.

- [ ] **Step 4: Write `src/webapp/data.py`**

```python
import dataclasses
import datetime
import json

from src.config import Settings, settings as default_settings
from src.models import BranchFeatures, Community, CommunityAssignment, Decision, NetworkStats


@dataclasses.dataclass
class BaselineData:
    features: list[BranchFeatures]
    decisions: list[Decision]
    assignments: list[CommunityAssignment]
    communities: list[Community]
    network: NetworkStats
    model_backend: str
    data_sources: dict[str, str]
    pipeline_run_at: datetime.datetime

    def decision_for(self, branch_id: str) -> Decision | None:
        return next((d for d in self.decisions if d.branch_id == branch_id), None)

    def communities_by_id(self) -> dict[str, Community]:
        return {c.id: c for c in self.communities}


def load_baseline(settings: Settings | None = None) -> BaselineData:
    settings = settings or default_settings
    processed_dir = settings.processed_dir

    payload = json.loads((processed_dir / "branch_features.json").read_text())
    network = NetworkStats(**payload["network"])
    features = [BranchFeatures(**b) for b in payload["branches"]]
    decisions = [Decision(**d) for d in
                 json.loads((processed_dir / "decisions.json").read_text())]
    assignments = [CommunityAssignment(**a) for a in
                   json.loads((processed_dir / "community_assignment.json").read_text())]
    communities = [Community(**c) for c in
                   json.loads((processed_dir / "communities.json").read_text())]

    run_meta_path = processed_dir / "run_meta.json"
    if run_meta_path.exists():
        model_backend = json.loads(run_meta_path.read_text())["model_backend"]
    else:
        model_backend = settings.model_backend

    data_sources = {
        "branches": "seed" if not settings.enable_scrape else "seed (scrape unimplemented)",
        "communities": "seed" if not settings.dubai_pulse_enabled
                        else "seed (pulse unimplemented)",
    }
    mtime = (processed_dir / "branch_features.json").stat().st_mtime

    return BaselineData(
        features=features, decisions=decisions, assignments=assignments,
        communities=communities, network=network, model_backend=model_backend,
        data_sources=data_sources, pipeline_run_at=datetime.datetime.fromtimestamp(mtime),
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/webapp/test_data.py -v`
Expected: both tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/webapp/__init__.py src/webapp/data.py tests/webapp/__init__.py tests/webapp/test_data.py
git commit -m "Add src/webapp/data.py baseline loader"
```

---

### Task 4: `src/webapp/map.py` — pydeck layer builders

**Files:**
- Create: `src/webapp/map.py`
- Create: `tests/webapp/test_map.py`

**Interfaces:**
- Consumes: `BranchFeatures`, `Community`, `CommunityAssignment`, `Decision` (`src.models`), `ScenarioDiff` (`src.scenario.models`).
- Produces (consumed by Task 7's page 1): `branch_layer(features, decisions) -> pdk.Layer`, `community_layer(communities, assignments, branch_actions) -> pdk.Layer`, `assignment_lines_layer(communities, assignments, features) -> pdk.Layer`, `sibling_lines_layer(selected, features) -> pdk.Layer`, `diff_highlight_layers(diff, features) -> list[pdk.Layer]`, `build_deck(layers: list[pdk.Layer]) -> pdk.Deck`, and constant `ACTION_COLORS: dict[str, list[int]]`.

pydeck ships bundled with Streamlit, so no new dependency is added here — `import pydeck` works once `streamlit` is installed (Task 10 adds it to `pyproject.toml`; until then, run this task's tests inside an environment that already has `streamlit` installed via `uv add streamlit --no-sync` or simply do Task 10's dependency step first if `pydeck` isn't importable — check with `uv run python -c "import pydeck"` before starting).

- [ ] **Step 0: Confirm pydeck is importable**

Run: `uv run python -c "import pydeck; print(pydeck.__version__)"`
If this fails with `ModuleNotFoundError`, run `uv add streamlit` now (this pulls in `pydeck`
as a transitive dependency) before continuing — Task 10 will also add `streamlit` to
`pyproject.toml` explicitly, so this isn't duplicated work, just sequenced earlier.

- [ ] **Step 1: Write the failing tests**

Create `tests/webapp/test_map.py`:

```python
from src.models import BranchFeatures, Community, CommunityAssignment, Decision
from src.scenario.models import BranchDiffEntry, CommunityDiffEntry, ScenarioDiff
from src.webapp.map import (
    ACTION_COLORS, assignment_lines_layer, branch_layer, build_deck,
    community_layer, diff_highlight_layers, sibling_lines_layer,
)


def _feature(branch_id, lat, lng, pop=1000):
    return BranchFeatures(
        branch_id=branch_id, name=branch_id, lat=lat, lng=lng, female_pop_served=pop,
        communities_served=1, mean_distance_km=1.0, max_distance_km=1.0, contested_pop=0,
        contested_share=0.0, nearest_sibling_km=1.0, siblings_within_5km=0, avg_price_aed=100.0,
        price_index=1.0, rating=4.5, review_count=10, pop_per_1k_rank=1, estimated_fields=[],
    )


def test_branch_layer_colors_by_action():
    features = [_feature("a", 25.0, 55.0)]
    decisions = [Decision(branch_id="a", action="SHRINK", confidence="medium",
                           rationale="r", key_drivers=[], caveats=[])]
    layer = branch_layer(features, decisions)
    assert layer.data[0]["color"] == ACTION_COLORS["SHRINK"]
    assert layer.data[0]["branch_id"] == "a"


def test_community_layer_inherits_assigned_branch_action():
    communities = [Community(id="c1", name_en="C1", lat=25.01, lng=55.01,
                              population_total=1000, population_female=500, is_estimated=False)]
    assignments = [CommunityAssignment(community_id="c1", nearest_branch_id="a", nearest_km=1.0,
                                        second_branch_id=None, second_km=None, contested=False,
                                        female_pop=500)]
    layer = community_layer(communities, assignments, {"a": "PROTECT"})
    assert layer.data[0]["color"][:3] == ACTION_COLORS["PROTECT"]


def test_assignment_lines_layer_connects_community_to_branch():
    features = [_feature("a", 25.0, 55.0)]
    communities = [Community(id="c1", name_en="C1", lat=25.01, lng=55.01,
                              population_total=1000, population_female=500, is_estimated=False)]
    assignments = [CommunityAssignment(community_id="c1", nearest_branch_id="a", nearest_km=1.0,
                                        second_branch_id=None, second_km=None, contested=False,
                                        female_pop=500)]
    layer = assignment_lines_layer(communities, assignments, features)
    assert layer.data[0]["target"] == [55.0, 25.0]


def test_sibling_lines_layer_only_includes_branches_within_5km():
    selected = _feature("a", 25.0, 55.0)
    near = _feature("b", 25.01, 55.01)   # ~1.5km away
    far = _feature("c", 26.0, 56.0)      # far away
    layer = sibling_lines_layer(selected, [selected, near, far])
    targets = [row["target"] for row in layer.data]
    assert [near.lng, near.lat] in targets
    assert [far.lng, far.lat] not in targets


def test_diff_highlight_layers_separates_new_ring_and_relocation():
    features = [_feature("a", 25.0, 55.0)]
    diff = ScenarioDiff(
        scenario_name="s",
        branches=[
            BranchDiffEntry(branch_id="a", old={"action": "PROTECT", "lat": 25.0, "lng": 55.0},
                             new={"action": "SHRINK", "lat": 25.5, "lng": 55.5},
                             changed_fields={"lat": {"old": 25.0, "new": 25.5},
                                             "lng": {"old": 55.0, "new": 55.5}},
                             action_changed=True),
            BranchDiffEntry(branch_id="new-branch", old=None,
                             new={"action": "HOLD", "lat": 25.2, "lng": 55.2,
                                  "female_pop_served": 0},
                             changed_fields={}, action_changed=True),
        ],
        communities=[CommunityDiffEntry(community_id="c1", reassigned=False,
                                         old_branch_id="a", new_branch_id="a")],
        baseline_backend="rubric", current_backend="rubric",
    )
    layers = diff_highlight_layers(diff, features)
    ring_layer, new_layer, move_layer = layers
    assert len(ring_layer.data) == 1
    assert len(new_layer.data) == 1
    assert len(move_layer.data) == 1
    assert move_layer.data[0]["source"] == [55.0, 25.0]
    assert move_layer.data[0]["target"] == [55.5, 25.5]


def test_build_deck_assembles_layers():
    deck = build_deck([branch_layer([_feature("a", 25.0, 55.0)], [])])
    assert len(deck.layers) == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/webapp/test_map.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.webapp.map'`.

- [ ] **Step 3: Write `src/webapp/map.py`**

```python
"""pydeck layer builders for the Dubai branch map. st.pydeck_chart (wired in
src/webapp/pages/product.py) renders whatever Deck build_deck() assembles.

Radii are in pixels (radius_units="pixels"), not meters, mirroring the previous Leaflet
circleMarker sizing -- zoom-invariant marker size, same visual language as before.
"""
import math

import pydeck as pdk

from src.models import BranchFeatures, Community, CommunityAssignment, Decision
from src.scenario.models import ScenarioDiff

ACTION_COLORS: dict[str, list[int]] = {
    "PROTECT": [46, 125, 50],
    "HOLD": [249, 168, 37],
    "SHRINK": [198, 40, 40],
}
DEFAULT_COLOR = [153, 153, 153]
DUBAI_VIEW = pdk.ViewState(latitude=25.2048, longitude=55.2708, zoom=11)


def _pop_radius(pop: float) -> float:
    return max(6.0, min(30.0, math.sqrt(max(pop, 0)) / 8))


def branch_layer(features: list[BranchFeatures], decisions: list[Decision]) -> pdk.Layer:
    decisions_by_id = {d.branch_id: d for d in decisions}
    rows = []
    for f in features:
        decision = decisions_by_id.get(f.branch_id)
        action = decision.action if decision else "HOLD"
        rows.append({
            "branch_id": f.branch_id, "name": f.name, "lat": f.lat, "lng": f.lng,
            "action": action, "radius": _pop_radius(f.female_pop_served),
            "color": ACTION_COLORS.get(action, DEFAULT_COLOR),
        })
    return pdk.Layer(
        "ScatterplotLayer", data=rows, get_position=["lng", "lat"], get_radius="radius",
        radius_units="pixels", get_fill_color="color", pickable=True, id="branches",
    )


def community_layer(communities: list[Community], assignments: list[CommunityAssignment],
                     branch_actions: dict[str, str]) -> pdk.Layer:
    assignment_by_id = {a.community_id: a for a in assignments}
    rows = []
    for c in communities:
        assignment = assignment_by_id.get(c.id)
        action = branch_actions.get(assignment.nearest_branch_id) if assignment else None
        color = ACTION_COLORS.get(action, DEFAULT_COLOR)
        pop = assignment.female_pop if assignment else 0
        opacity = min(1.0, max(0.2, pop / 20000))
        rows.append({"lat": c.lat, "lng": c.lng, "color": [*color, int(opacity * 255)]})
    return pdk.Layer(
        "ScatterplotLayer", data=rows, get_position=["lng", "lat"], get_radius=4,
        radius_units="pixels", get_fill_color="color", id="communities",
    )


def assignment_lines_layer(communities: list[Community], assignments: list[CommunityAssignment],
                            features: list[BranchFeatures]) -> pdk.Layer:
    branch_by_id = {f.branch_id: f for f in features}
    community_by_id = {c.id: c for c in communities}
    rows = []
    for a in assignments:
        branch = branch_by_id.get(a.nearest_branch_id)
        community = community_by_id.get(a.community_id)
        if not branch or not community:
            continue
        rows.append({"source": [community.lng, community.lat], "target": [branch.lng, branch.lat]})
    return pdk.Layer(
        "LineLayer", data=rows, get_source_position="source", get_target_position="target",
        get_color=[136, 136, 136], get_width=1, id="assignment-lines",
    )


def sibling_lines_layer(selected: BranchFeatures, features: list[BranchFeatures]) -> pdk.Layer:
    rows = []
    for other in features:
        if other.branch_id == selected.branch_id:
            continue
        km = math.hypot(selected.lat - other.lat, selected.lng - other.lng) * 111
        if km <= 5.0:
            rows.append({"source": [selected.lng, selected.lat],
                         "target": [other.lng, other.lat]})
    return pdk.Layer(
        "LineLayer", data=rows, get_source_position="source", get_target_position="target",
        get_color=[85, 85, 85], get_width=1, id="sibling-lines",
    )


def diff_highlight_layers(diff: ScenarioDiff, features: list[BranchFeatures]) -> list[pdk.Layer]:
    feature_by_id = {f.branch_id: f for f in features}
    ring_rows, new_rows, move_rows = [], [], []

    for entry in diff.branches:
        if entry.old is None and entry.new is not None:
            new_rows.append({
                "lat": entry.new["lat"], "lng": entry.new["lng"],
                "color": [*ACTION_COLORS.get(entry.new["action"], DEFAULT_COLOR), 140],
            })
            continue
        if not (entry.action_changed or entry.changed_fields):
            continue
        branch = feature_by_id.get(entry.branch_id)
        if branch is None:
            continue
        color = ACTION_COLORS.get(entry.new["action"], [0, 0, 0]) if entry.action_changed else [0, 0, 0]
        ring_rows.append({
            "lat": branch.lat, "lng": branch.lng,
            "radius": _pop_radius(branch.female_pop_served) + 6, "color": color,
        })
        lat_change = entry.changed_fields.get("lat")
        lng_change = entry.changed_fields.get("lng")
        if lat_change or lng_change:
            old_lat = lat_change["old"] if lat_change else branch.lat
            old_lng = lng_change["old"] if lng_change else branch.lng
            move_rows.append({
                "source": [old_lng, old_lat],
                "target": [entry.new["lng"], entry.new["lat"]],
            })

    return [
        pdk.Layer("ScatterplotLayer", data=ring_rows, get_position=["lng", "lat"],
                  get_radius="radius", radius_units="pixels", filled=False, stroked=True,
                  get_line_color="color", line_width_min_pixels=3, id="diff-rings"),
        pdk.Layer("ScatterplotLayer", data=new_rows, get_position=["lng", "lat"], get_radius=10,
                  radius_units="pixels", get_fill_color="color", id="diff-new-branches"),
        pdk.Layer("LineLayer", data=move_rows, get_source_position="source",
                  get_target_position="target", get_color=[21, 101, 192], get_width=2,
                  id="diff-relocations"),
    ]


def build_deck(layers: list[pdk.Layer]) -> pdk.Deck:
    return pdk.Deck(
        layers=layers, initial_view_state=DUBAI_VIEW, map_style=None,
        tooltip={"html": "<b>{name}</b><br/>{action}"},
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/webapp/test_map.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/webapp/map.py tests/webapp/test_map.py
git commit -m "Add src/webapp/map.py pydeck layer builders"
```

---

### Task 5: `src/webapp/scenario_editor.py` — widget-based scenario builder

**Files:**
- Create: `src/webapp/scenario_editor.py`
- Create: `tests/webapp/test_scenario_editor.py`

**Interfaces:**
- Consumes: `Branch` (`src.models`), `Scenario`, `ScenarioAssumptions`, `ScenarioOverrides` (`src.scenario.models`).
- Produces (consumed by Task 7's page 1): `render_assumptions() -> None`, `render_branch_override(existing_branches: dict[str, Branch]) -> None`, `pending_overrides_summary() -> list[str]`, `clear_overrides() -> None`, `build_scenario(name: str = "live-scenario") -> Scenario`. All read/write `st.session_state` under the keys `branch_overrides`, `community_overrides`, `contest_ratio`, `model_backend`.

Uses `streamlit.testing.v1.AppTest`, which runs a real Streamlit script in-process and lets
tests interact with widgets exactly as a user would — this is the only way to test code that
calls `st.slider`/`st.button`/etc. directly.

- [ ] **Step 1: Write the failing tests**

Create `tests/webapp/test_scenario_editor.py`:

```python
from streamlit.testing.v1 import AppTest

SCRIPT = """
import streamlit as st

from src.models import Branch
from src.webapp.scenario_editor import (
    build_scenario, clear_overrides, render_assumptions, render_branch_override,
)

existing = {
    "a": Branch(id="a", name="Branch A", lat=25.0, lng=55.0, area="Area A",
                rating=4.5, review_count=10, avg_price_aed=99.0, source="seed"),
}

render_assumptions()
render_branch_override(existing)
if st.button("Clear"):
    clear_overrides()
st.session_state["_scenario"] = build_scenario()
"""


def test_assumptions_default_to_rubric_and_baseline_contest_ratio():
    at = AppTest.from_string(SCRIPT)
    at.run()
    scenario = at.session_state["_scenario"]
    assert scenario.assumptions.model_backend == "rubric"


def test_applying_an_override_updates_the_scenario():
    at = AppTest.from_string(SCRIPT)
    at.run()
    at.slider(key="rating-a").set_value(2.0).run()
    at.button(key="apply-a").click().run()
    scenario = at.session_state["_scenario"]
    assert scenario.overrides.branches["a"]["rating"] == 2.0


def test_clear_overrides_empties_the_scenario():
    at = AppTest.from_string(SCRIPT)
    at.run()
    at.slider(key="rating-a").set_value(2.0).run()
    at.button(key="apply-a").click().run()
    at.button(key="Clear").click().run()
    scenario = at.session_state["_scenario"]
    assert scenario.overrides.branches == {}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/webapp/test_scenario_editor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.webapp.scenario_editor'`.

- [ ] **Step 3: Write `src/webapp/scenario_editor.py`**

```python
"""Widget-based scenario authoring. Every render_* function reads/writes
st.session_state directly (Streamlit's own state-across-reruns mechanism) rather than
returning values up a call chain, since widgets themselves only exist mid-script-run.
build_scenario() is the single place that turns accumulated session_state into the
Scenario object src.scenario.run.run_scenario() actually consumes.
"""
import streamlit as st

from src.models import Branch
from src.scenario.models import Scenario, ScenarioAssumptions, ScenarioOverrides

NEW_BRANCH_LABEL = "(new hypothetical branch)"


def _init_session_state() -> None:
    st.session_state.setdefault("branch_overrides", {})
    st.session_state.setdefault("community_overrides", {})
    st.session_state.setdefault("contest_ratio", 1.25)
    st.session_state.setdefault("model_backend", "rubric")


def render_assumptions() -> None:
    _init_session_state()
    st.session_state["contest_ratio"] = st.slider(
        "Contest ratio", min_value=1.0, max_value=2.0,
        value=st.session_state["contest_ratio"], step=0.05,
        help="A community counts as 'contested' when its second-nearest branch is within "
             "this ratio of its nearest.",
    )
    backend_options = ["rubric", "llm"]
    st.session_state["model_backend"] = st.radio(
        "Decision backend", options=backend_options,
        index=backend_options.index(st.session_state["model_backend"]),
        help="rubric is free, instant, and deterministic. llm costs a real API call per "
             "branch and needs ANTHROPIC_API_KEY configured -- its cache never helps across "
             "different scenarios, so rubric is the default for perturbation runs.",
    )


def render_branch_override(existing_branches: dict[str, Branch]) -> None:
    _init_session_state()
    branch_ids = sorted(existing_branches)
    choice = st.selectbox("Branch to add or override", options=[NEW_BRANCH_LABEL, *branch_ids])

    if choice == NEW_BRANCH_LABEL:
        branch_id = st.text_input("New branch id", key="new-branch-id",
                                   placeholder="e.g. dubai-marina-new")
        name = st.text_input("Name", value="Hypothetical Branch", key="new-branch-name")
        lat = st.number_input("Latitude", value=25.2048, format="%.4f", key="new-branch-lat")
        lng = st.number_input("Longitude", value=55.2708, format="%.4f", key="new-branch-lng")
        area = st.text_input("Area", value="", key="new-branch-area")
        rating = st.slider("Rating", 0.0, 5.0, 4.0, 0.1, key="new-branch-rating")
        price = st.number_input("Avg price (AED)", value=99.0, min_value=0.0,
                                 key="new-branch-price")
        if st.button("Add branch", key="add-new-branch") and branch_id:
            st.session_state["branch_overrides"][branch_id] = {
                "name": name, "lat": lat, "lng": lng, "area": area,
                "rating": rating, "avg_price_aed": price,
            }
    else:
        current = existing_branches[choice]
        rating = st.slider("Rating", 0.0, 5.0, current.rating or 4.0, 0.1, key=f"rating-{choice}")
        price = st.number_input("Avg price (AED)", value=current.avg_price_aed or 99.0,
                                 min_value=0.0, key=f"price-{choice}")
        lat = st.number_input("Latitude", value=current.lat, format="%.4f", key=f"lat-{choice}")
        lng = st.number_input("Longitude", value=current.lng, format="%.4f", key=f"lng-{choice}")
        if st.button("Apply override", key=f"apply-{choice}"):
            st.session_state["branch_overrides"][choice] = {
                "rating": rating, "avg_price_aed": price, "lat": lat, "lng": lng,
            }


def pending_overrides_summary() -> list[str]:
    _init_session_state()
    return [f"{bid}: {patch}" for bid, patch in st.session_state["branch_overrides"].items()]


def clear_overrides() -> None:
    st.session_state["branch_overrides"] = {}
    st.session_state["community_overrides"] = {}
    st.session_state["contest_ratio"] = 1.25
    st.session_state["model_backend"] = "rubric"


def build_scenario(name: str = "live-scenario") -> Scenario:
    _init_session_state()
    return Scenario(
        name=name,
        assumptions=ScenarioAssumptions(
            contest_ratio=st.session_state["contest_ratio"],
            model_backend=st.session_state["model_backend"],
        ),
        overrides=ScenarioOverrides(
            branches=st.session_state["branch_overrides"],
            communities=st.session_state["community_overrides"],
        ),
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/webapp/test_scenario_editor.py -v`
Expected: all 3 tests PASS. If a widget `key` lookup fails, double check the test script's
`key=` strings match the ones in `scenario_editor.py` exactly (`AppTest` looks widgets up by
key, not by label).

- [ ] **Step 5: Commit**

```bash
git add src/webapp/scenario_editor.py tests/webapp/test_scenario_editor.py
git commit -m "Add src/webapp/scenario_editor.py widget-based scenario builder"
```

---

### Task 6: Streamlit entrypoint, navigation, and config/secrets scaffolding

**Files:**
- Create: `streamlit_app.py`
- Create: `src/webapp/pages/__init__.py` (empty)
- Create: `src/webapp/pages/product.py` (stub — fleshed out in Task 7)
- Create: `src/webapp/pages/model.py` (stub — fleshed out in Task 8)
- Create: `src/webapp/pages/story.py` (stub — fleshed out in Task 9)
- Create: `.streamlit/config.toml`
- Create: `.streamlit/secrets.toml.example`
- Modify: `.gitignore`
- Create: `tests/webapp/test_pages.py`

**Interfaces:**
- Produces: each page module exposes `render() -> None`, called by `st.Page(module.render, ...)` in `streamlit_app.py`. Page order is the literal order of the list: product, model, story.

- [ ] **Step 1: Write the failing test**

Create `tests/webapp/test_pages.py`:

```python
from streamlit.testing.v1 import AppTest


def test_app_loads_without_exception():
    at = AppTest.from_file("streamlit_app.py")
    at.run()
    assert not at.exception
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/webapp/test_pages.py -v`
Expected: FAIL (`streamlit_app.py` doesn't exist yet).

- [ ] **Step 3: Create the stub page modules**

Create `src/webapp/pages/__init__.py` (empty).

Create `src/webapp/pages/product.py`:

```python
import streamlit as st


def render() -> None:
    st.title("The Product")
    st.write("Live demo content lands here in a later task.")
```

Create `src/webapp/pages/model.py`:

```python
import streamlit as st


def render() -> None:
    st.title("Model, Assumptions & Data")
    st.write("Methodology and data-provenance content lands here in a later task.")
```

Create `src/webapp/pages/story.py`:

```python
import streamlit as st


def render() -> None:
    st.title("Why This Exists")
    st.write("Narrative content lands here in a later task.")
```

- [ ] **Step 4: Create `streamlit_app.py`**

```python
import streamlit as st

from src.webapp.pages import model, product, story

st.set_page_config(page_title="Bedashing Branch Right-Sizing", layout="wide")

pages = [
    st.Page(product.render, title="The Product", icon="🗺️", default=True),
    st.Page(model.render, title="Model, Assumptions & Data", icon="📊"),
    st.Page(story.render, title="Why This Exists", icon="📝"),
]
st.navigation(pages).run()
```

- [ ] **Step 5: Create `.streamlit/config.toml`**

```toml
[client]
toolbarMode = "minimal"

[theme]
base = "light"
```

- [ ] **Step 6: Create `.streamlit/secrets.toml.example`**

```toml
# Copy to .streamlit/secrets.toml (gitignored) for local dev. On Streamlit Community
# Cloud, set the same key via the app's "Secrets" panel instead of committing this file.
ANTHROPIC_API_KEY = "sk-ant-..."
```

- [ ] **Step 7: Update `.gitignore`**

Add this line:
```
.streamlit/secrets.toml
```

- [ ] **Step 8: Run the test to verify it passes**

Run: `uv run pytest tests/webapp/test_pages.py -v`
Expected: PASS.

- [ ] **Step 9: Manually verify navigation in a browser**

Run: `uv run streamlit run streamlit_app.py`
Open the printed local URL. Confirm all three pages appear in the sidebar in the order
Product, Model, Story, and each renders its stub text without error. Stop the server
(Ctrl+C) once confirmed.

- [ ] **Step 10: Commit**

```bash
git add streamlit_app.py src/webapp/pages .streamlit tests/webapp/test_pages.py .gitignore
git commit -m "Add Streamlit entrypoint, navigation, and config/secrets scaffolding"
```

---

### Task 7: Page 1 — "The Product" (headline + live demo)

**Files:**
- Modify: `src/webapp/pages/product.py`
- Modify: `tests/webapp/test_pages.py`

**Interfaces:**
- Consumes: `load_baseline` (`src.webapp.data`), `branch_layer`/`community_layer`/`assignment_lines_layer`/`sibling_lines_layer`/`diff_highlight_layers`/`build_deck` (`src.webapp.map`), `render_assumptions`/`render_branch_override`/`clear_overrides`/`build_scenario` (`src.webapp.scenario_editor`), `run_scenario` (`src.scenario.run`).
- This task has no downstream consumers — it's the top of the dependency chain.

This is the main integration task. Fold the headline block and the live demo into one
`render()`:

- [ ] **Step 1: Write `src/webapp/pages/product.py`**

```python
import collections

import streamlit as st

from src.config import settings
from src.models import Branch
from src.scenario.run import run_scenario
from src.webapp.data import load_baseline
from src.webapp.map import (
    assignment_lines_layer, branch_layer, build_deck, community_layer,
    diff_highlight_layers, sibling_lines_layer,
)
from src.webapp.scenario_editor import (
    build_scenario, clear_overrides, pending_overrides_summary, render_assumptions,
    render_branch_override,
)


def _headline(data) -> dict:
    counts = collections.Counter(d.action for d in data.decisions)
    shrink_ids = {d.branch_id for d in data.decisions if d.action == "SHRINK"}
    shrink_drivers = collections.Counter(
        driver for d in data.decisions if d.branch_id in shrink_ids for driver in d.key_drivers
    )
    return {
        "protect": counts.get("PROTECT", 0),
        "hold": counts.get("HOLD", 0),
        "shrink": counts.get("SHRINK", 0),
        "total": len(data.decisions),
        "top_shrink_drivers": [driver for driver, _ in shrink_drivers.most_common(2)],
    }


def _render_headline(data) -> None:
    h = _headline(data)
    st.header("The recommendation")
    st.markdown(
        f"Of **{h['total']} branches** in Bedashing's Dubai network: "
        f"**{h['protect']} PROTECT**, **{h['hold']} HOLD**, **{h['shrink']} SHRINK**."
    )
    if h["top_shrink_drivers"]:
        drivers = " and ".join(h["top_shrink_drivers"])
        st.markdown(f"SHRINK calls are driven primarily by **{drivers}**.")
    st.caption(
        f"Backend: {data.model_backend} · pipeline run at "
        f"{data.pipeline_run_at:%Y-%m-%d %H:%M} · "
        "every price and population figure in this dataset is an estimate, not a reported "
        "figure — see the Model page for exactly which fields and why."
    )


def _render_detail_panel(feature, decision) -> None:
    st.subheader(feature.name)
    if decision:
        st.markdown(f"**{decision.action}** ({decision.confidence} confidence)")
        st.write(decision.rationale)
        st.markdown(f"**Key drivers:** {', '.join(decision.key_drivers)}")
    st.table({
        "Feature": ["Female pop served", "Contested share", "Avg price (AED)", "Rating",
                    "Communities served"],
        "Value": [feature.female_pop_served, round(feature.contested_share, 2),
                  feature.avg_price_aed, feature.rating, feature.communities_served],
    })
    if decision and decision.caveats:
        st.caption("Caveats: " + "; ".join(decision.caveats))


def render() -> None:
    st.title("The Product")
    data = load_baseline(settings)
    _render_headline(data)

    st.divider()
    st.subheader("The evidence — stress-test the assumptions yourself")

    show_communities = st.checkbox("Show communities", value=True)
    show_assignment_lines = st.checkbox("Show assignment lines", value=False)

    branch_actions = {f.branch_id: (data.decision_for(f.branch_id).action
                                      if data.decision_for(f.branch_id) else "HOLD")
                       for f in data.features}

    layers = [branch_layer(data.features, data.decisions)]
    if show_communities:
        layers.append(community_layer(data.communities, data.assignments, branch_actions))
    if show_assignment_lines:
        layers.append(assignment_lines_layer(data.communities, data.assignments, data.features))

    scenario_run = st.session_state.get("scenario_run")
    if scenario_run:
        layers.extend(diff_highlight_layers(scenario_run.diff, data.features))

    event = st.pydeck_chart(build_deck(layers), on_select="rerun",
                             selection_mode="single-object", key="branch-map")

    selected_id = None
    objects = event.selection.get("objects", {}) if event else {}
    if objects.get("branches"):
        selected_id = objects["branches"][0]["branch_id"]

    if selected_id:
        feature = next(f for f in data.features if f.branch_id == selected_id)
        _render_detail_panel(feature, data.decision_for(selected_id))
        st.pydeck_chart(build_deck([branch_layer(data.features, data.decisions),
                                     sibling_lines_layer(feature, data.features)]))

    st.divider()
    st.subheader("Build a scenario")
    render_assumptions()
    existing_branches = {f.branch_id: Branch(id=f.branch_id, name=f.name, lat=f.lat, lng=f.lng,
                                              area="", rating=f.rating,
                                              review_count=f.review_count,
                                              avg_price_aed=f.avg_price_aed, source="seed")
                          for f in data.features}
    render_branch_override(existing_branches)

    pending = pending_overrides_summary()
    if pending:
        st.write("Pending overrides:", pending)

    col1, col2 = st.columns(2)
    if col1.button("Run scenario", type="primary"):
        scenario = build_scenario()
        st.session_state["scenario_run"] = run_scenario(scenario, settings)
        st.rerun()
    if col2.button("Reset to baseline"):
        clear_overrides()
        st.session_state.pop("scenario_run", None)
        st.rerun()

    if scenario_run:
        st.subheader("What changed")
        changed = [b for b in scenario_run.diff.branches if b.changed_fields or b.old is None]
        st.write(f"{len(changed)} branch(es) changed, "
                 f"{sum(1 for c in scenario_run.diff.communities if c.reassigned)} "
                 "community(ies) reassigned.")
        for entry in changed:
            st.write(f"**{entry.branch_id}**", entry.changed_fields)
```

- [ ] **Step 2: Add a page-1-specific smoke test**

Add to `tests/webapp/test_pages.py`:

```python
def test_app_product_page_shows_headline():
    at = AppTest.from_file("streamlit_app.py")
    at.run()
    assert not at.exception
    headers = [h.value for h in at.header]
    assert "The recommendation" in headers
```

- [ ] **Step 3: Run the tests**

Run: `uv run pytest tests/webapp/test_pages.py -v`
Expected: both tests PASS. This requires `data/processed/baseline/` to already exist —
run `just all` first if it doesn't (`AppTest` runs the real page against real on-disk data,
same as the browser would).

- [ ] **Step 4: Manually verify in a browser**

Run: `uv run streamlit run streamlit_app.py`. On the Product page: confirm the headline
sentence reads sensibly against the real baseline data, click a branch marker and confirm
the detail panel appears, add or override a branch, click "Run scenario," and confirm the
map updates with diff highlights. Click "Reset to baseline" and confirm the diff clears.
Stop the server once confirmed — do not report this task done without having actually
clicked through this flow.

- [ ] **Step 5: Commit**

```bash
git add src/webapp/pages/product.py tests/webapp/test_pages.py
git commit -m "Implement Page 1: headline + live perturbation demo"
```

---

### Task 8: Page 2 — "Model, Assumptions & Data"

**Files:**
- Modify: `src/webapp/pages/model.py`
- Modify: `tests/webapp/test_pages.py`

**Interfaces:**
- Consumes: `load_baseline` (`src.webapp.data`), `settings` (`src.config`).

Content ported verbatim from `docs/designs/v0.md`'s "What's actually in the seed data" and
the README's "Known limitations" section (both already quoted in full in this repo — copy
the facts, don't re-derive them).

- [ ] **Step 1: Write `src/webapp/pages/model.py`**

```python
import streamlit as st

from src.config import settings
from src.webapp.data import load_baseline

KNOWN_LIMITATIONS = [
    "Nearest-branch assignment is false. Real choice depends on travel time, malls, "
    "parking, habit, price and brand. Straight-line distance from a community centroid "
    "ignores all of it.",
    "Community centroids are not where people live. Large communities get collapsed to "
    "a point.",
    "No competitors. A branch with five rival salons next door looks identical to one "
    "with none. The single biggest omission.",
    "Female population is a poor demand proxy on its own — and every value in this "
    "dataset is an estimate (see Data provenance below), not just a proxy that could be "
    "refined.",
    "No revenue, footfall, staffing or lease data, so 'SHRINK' here cannot distinguish a "
    "badly-located branch from a well-located, badly-run one.",
    "The LLM classifies without ground truth and will produce confident-sounding labels "
    "regardless. Agreement with the rubric is a sanity check, not validation.",
    "Prices are not 'a thin basket that may not be current' — there are zero real "
    "per-branch prices anywhere, confirmed, not merely unsourced.",
    "Dubai only.",
]


def _render_pipeline() -> None:
    st.header("The pipeline")
    st.markdown(
        "Four independently re-runnable, file-based stages:\n\n"
        "`seed data -> acquire -> raw JSON -> features -> processed JSON -> model -> "
        "decisions`\n\n"
        "- **Acquire**: loads branch/community/price seed data, falling back to seed "
        "whenever live enrichment isn't available (it never is in this build — see Data "
        "provenance below).\n"
        "- **Features**: assigns every community to its nearest branch (haversine "
        "distance), rolls that up into per-branch features (population served, contested "
        "share, price index, sibling proximity) plus network-wide medians to compare "
        "against.\n"
        "- **Model**: a deterministic rubric (normalize population/contested-share/rating, "
        "equal-weight sum, top third PROTECT / bottom third SHRINK / rest HOLD) or an LLM "
        "backend (one Anthropic tool-use call per branch, disk-cached, rubric fallback on "
        "failure) label each branch.\n"
    )


def _render_data_provenance(data) -> None:
    st.header("Data provenance")
    st.markdown(
        "**9 real Dubai branches** (2GIS's UAE branch-aggregation page for ratings/reviews). "
        "**50 real Dubai communities**, population from the Dubai Statistics Center 2022/2024 "
        "Population Bulletin.\n\n"
        "**Every `avg_price_aed` is estimated.** No source checked (2GIS, Fresha, Groupon, "
        "social media, including a real browser rendering Fresha's pages directly) exposes a "
        "per-branch price for any of the 9 real branches. All 9 carry a single fallback "
        "constant (AED 99 — the one real Bedashing price point found anywhere, a chain-wide "
        "promo) and are flagged estimated.\n\n"
        "**Every `population_female` is estimated.** `dubaipulse.gov.ae` and `dsc.gov.ae` "
        "both block automated access, and the source Population Bulletin PDF doesn't publish "
        "a per-community gender split at all — only emirate-wide. All 50 communities' female "
        "population is estimated via a global 49% share and flagged as such."
    )
    st.caption(f"Configured data sources: branches={data.data_sources['branches']}, "
               f"communities={data.data_sources['communities']}")


def _render_backend_comparison() -> None:
    st.header("Rubric vs. LLM")
    if settings.anthropic_api_key:
        st.info("ANTHROPIC_API_KEY is configured — live rubric-vs-LLM agreement would run "
                "here in a future iteration.")
    else:
        st.markdown(
            "This public demo runs the **rubric backend only** — free, instant, "
            "deterministic, and exactly reproducible. The LLM backend is a real, working "
            "alternative (one Anthropic call per branch, structured output, disk-cached) "
            "but isn't exposed publicly here since it costs real API calls and its cache "
            "never helps across different scenarios."
        )


def _render_limitations() -> None:
    st.header("Known limitations")
    for item in KNOWN_LIMITATIONS:
        st.markdown(f"- {item}")


def render() -> None:
    st.title("Model, Assumptions & Data")
    data = load_baseline(settings)
    _render_pipeline()
    _render_data_provenance(data)
    _render_backend_comparison()
    _render_limitations()
```

- [ ] **Step 2: Add a page-2-specific smoke test**

Add to `tests/webapp/test_pages.py`:

```python
def test_app_model_page_lists_limitations():
    at = AppTest.from_file("streamlit_app.py")
    at.run()
    at.switch_page("src/webapp/pages/model.py")
    at.run()
    assert not at.exception
    headers = [h.value for h in at.header]
    assert "Known limitations" in headers
```

- [ ] **Step 3: Run the tests**

Run: `uv run pytest tests/webapp/test_pages.py -v`
Expected: PASS. If `at.switch_page` can't resolve the path, check the exact path
`st.Page` was constructed with in `streamlit_app.py` — `AppTest.switch_page` takes the
same path Streamlit itself uses internally for a callable `st.Page`, which is the source
file path of the module the callable is defined in.

- [ ] **Step 4: Manually verify in a browser**

Run: `uv run streamlit run streamlit_app.py`, click to the Model page, and read through it
— confirm nothing reads as a stub, and the data-provenance numbers match the real baseline
output.

- [ ] **Step 5: Commit**

```bash
git add src/webapp/pages/model.py tests/webapp/test_pages.py
git commit -m "Implement Page 2: model, assumptions, and data provenance"
```

---

### Task 9: Page 3 — "Why This Exists"

**Files:**
- Modify: `src/webapp/pages/story.py`
- Modify: `tests/webapp/test_pages.py`

**Interfaces:** None — pure static content, no data dependency.

- [ ] **Step 1: Write `src/webapp/pages/story.py`**

```python
import streamlit as st


def render() -> None:
    st.title("Why This Exists")

    st.header("The business question")
    st.markdown(
        "Bedashing Beauty Lounge operates multiple branches across Dubai. Which ones "
        "should be protected and invested in, which are fine as-is, and which are "
        "candidates for downsizing? That's the question this project answers — not with "
        "a slide deck, but with a running pipeline you can argue with."
    )

    st.header("Who this is for")
    st.markdown(
        "This is a submission for a technical analyst / implementer role at a private "
        "equity firm. The audience is consultants: time-constrained, and trained to expect "
        "the conclusion first, the evidence second, and the methodology available on "
        "request — which is exactly how this app is ordered. If you've read this far, "
        "you've already seen the recommendation (Product) and the mechanics behind it "
        "(Model, Assumptions & Data); this page is the reflective layer behind both: why "
        "a running tool, and why built this way."
    )

    st.header("Perturb, re-run, compare")
    st.markdown(
        "A model is only useful if you can argue with it. The core interaction here isn't "
        "'view the report' — it's change an assumption or a signal you think is wrong, "
        "rerun the same model against the changed input, and see exactly what moved: which "
        "branches flipped, by how much, and why. The report isn't a one-shot output; it's "
        "the left half of a diff whose right half you control. That's what the scenario "
        "editor on the Product page is for — not a tech demo, but sensitivity analysis, "
        "the same instinct diligence work runs on."
    )

    st.header("How this evolved")
    st.markdown(
        "- **v0** — a deliberately crude, end-to-end prototype: seed data in, a map with "
        "PROTECT/HOLD/SHRINK labels out. The point was a working toy to poke at, not a "
        "defensible model.\n"
        "- **v1** — added baseline-vs-scenario diffing: declare a baseline explicitly, "
        "perturb assumptions or signals in a hand-edited YAML file, rerun, and diff against "
        "baseline at both the branch and community level.\n"
        "- **This app** — v1's own design doc named an interactive override UI as explicit "
        "future work, deferred for later. This is that UI, built natively in Streamlit "
        "instead of a custom frontend, so perturbing a scenario is a slider, not a YAML "
        "edit."
    )
```

- [ ] **Step 2: Add a page-3-specific smoke test**

Add to `tests/webapp/test_pages.py`. **Do not use `AppTest.switch_page()` here** — it
only matches pages registered with a file-path `script_path`; every page in this app is
registered via `st.Page(callable, ...)` (see `streamlit_app.py`), whose `script_path` is
always `""`, so `switch_page` can never find them (confirmed against the installed
streamlit's `navigation.py`/`app_test.py` source during Task 8's review). Use
`AppTest.from_function` with a small wrapper that imports `streamlit` and the page's
`render` itself, which actually executes `render()` through real Streamlit script-running
machinery instead of only re-checking the default page:

```python
def test_app_story_page_explains_evolution():
    def run_story_page():
        import streamlit as st
        from src.webapp.pages.story import render
        render()

    at = AppTest.from_function(run_story_page)
    at.run()
    assert not at.exception
    headers = [h.value for h in at.header]
    assert "How this evolved" in headers
```

- [ ] **Step 3: Run the tests**

Run: `uv run pytest tests/webapp/test_pages.py -v`
Expected: PASS.

- [ ] **Step 4: Manually verify in a browser**

Run: `uv run streamlit run streamlit_app.py`, click to the Story page, read it end to end.

- [ ] **Step 5: Commit**

```bash
git add src/webapp/pages/story.py tests/webapp/test_pages.py
git commit -m "Implement Page 3: narrative and project evolution"
```

---

### Task 10: Dependencies, requirements.txt, and README

**Files:**
- Modify: `pyproject.toml`
- Create: `requirements.txt`
- Modify: `README.md`

**Interfaces:** None — this is the deployment-readiness and documentation pass, the last
task before the final whole-branch review.

- [ ] **Step 1: Add `streamlit` to `pyproject.toml`**

In the `dependencies` list, add:
```
    "streamlit>=1.38",
```

(`>=1.38` is the floor for `st.Page`/`st.navigation` with callables and `on_select` on
`st.pydeck_chart` — confirm the installed version satisfies this with
`uv run python -c "import streamlit; print(streamlit.__version__)"` after the next step.)

- [ ] **Step 2: Sync and regenerate the lockfile**

Run: `uv sync --extra dev`
Expected: resolves and installs `streamlit` (and its transitive `pydeck`) successfully.

- [ ] **Step 3: Generate `requirements.txt` for Streamlit Community Cloud**

Run: `uv export --no-dev --no-hashes --format requirements-txt > requirements.txt`
This is committed alongside `pyproject.toml`/`uv.lock` specifically for Streamlit
Community Cloud's dependency resolver, which doesn't read `uv.lock`.

- [ ] **Step 4: Update `README.md`**

Replace the "Run everything" and "Perturb an assumption or a signal (v1)" sections'
references to `just serve` / the FastAPI+Leaflet frontend with:

```markdown
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
```

Update "Known limitations" in the README to say: "See the Model, Assumptions & Data page
of the deployed app." (the full list now lives there, not duplicated in the README).

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest`
Expected: all tests pass (acquire, features, model, scenario, config, webapp — everything).

- [ ] **Step 6: Run ruff**

Run: `uv run ruff check src tests streamlit_app.py`
Fix any lint findings.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock requirements.txt README.md
git commit -m "Add streamlit dependency, requirements.txt, and updated README"
```

---

## After all tasks: final review and deployment

1. Dispatch a final whole-branch code review (per `superpowers:subagent-driven-development`)
   covering the full diff against the branch's start point.
2. Manually run `uv run streamlit run streamlit_app.py` one more time and click through all
   three pages and the full perturbation flow end to end — this is the step that actually
   verifies the UI works, not just that `AppTest` didn't raise.
3. Use `superpowers:finishing-a-development-branch` to merge/PR the work.
4. Deployment to Streamlit Community Cloud is a manual, browser-only step only the repo
   owner can do (no CLI/API exists for it) — hand off the three values (repo, branch, main
   file path `streamlit_app.py`) once the branch is merged or ready for preview.
