# Integration Implementation Plan: the app on the v3 market model

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Streamlit app runs on `data/seed/v3/` and the market model: all 24 UAE lounges, drive-time catchments, women 15+ per cell, capture among premium substitutes, and growth areas, with every assumption visible. The old hand-curated seed and its code are removed.

**Architecture:** The pipeline keeps its three stages and the app keeps its three pages, but each stage is rewritten for the new data. (1) `src/market.py` holds the market-model maths, moved out of `scripts/` with their tests. (2) `src/features/build.py` turns the committed v3 files plus a set of assumption *levels* (travel time, coverage, worker-housing share, recall) and an optional set of *closed* lounges into lounge features and growth areas: all precomputed, no API calls at runtime. (3) `src/model/rubric.py` scores four new signals on fixed scales into PROTECT / HOLD / SHRINK; `src/model/opportunity.py` labels growth areas GROW / WATCH / SKIP on population and distance. Scenarios become "switch an assumption level, or close a lounge". The explanation layer gets a new glossary and its cache is regenerated.

**Tech Stack:** Python 3.11+, pydantic, Streamlit + pydeck (existing), shapely (map polygons), pandas, the Anthropic API for `just explain` (existing).

**Spec:** `docs/remaining.md`, "Data refresh (v3)" → "Spec for the integration plan", plus the decisions taken on 2026-10-09:

| Decision | Answer |
|---|---|
| What-ifs | **Switch assumption levels + close a lounge.** All precomputed; no API calls at runtime; works on the public deploy. Moving or adding a lounge is dropped (it needs live Mapbox/Google calls) |
| Rating signal | **Relative to the lounge's substitutes:** lounge rating minus the median rating of its premium substitutes |
| Growth areas | **Population and distance only:** populated cells outside every lounge's catchment, grouped into named areas. No competitor data outside catchments; stated as a limitation |
| Branch decision | **Same scorecard, new signals:** fixed-scale, equal-weight composite of four 0-1 scores; PROTECT ≥ 0.65, SHRINK ≤ 0.35 |

## Global Constraints

- **No API calls at runtime or in tests.** The app and pipeline read only committed files. `scripts/` (the fetchers) are not called by the app.
- **Every tunable value lives in `data/scenarios/baseline.yaml`** and is shown in the app next to the numbers it drives.
- **The live deploy is `main`.** All work happens on `data-refresh`; merging to `main` is the last step and needs the user's go-ahead.
- **Tests stay green at the end of every task** (`just test`). Tests for deleted code are deleted with it, not skipped.
- **Explanations:** regenerating the cache (`just explain`) needs `ANTHROPIC_API_KEY` and costs money (~50 subjects on Opus 5.5 at low effort; expect well under $5). Ask before running it.
- **Don't reference the old seed** in new notebooks, docs or app text (it's deleted in Task 9).
- Commit and push after each task (user preference: never risk losing work).

## Review Focus

1. **A closed lounge.** Closing one must remove it from every other lounge's substitute set, re-count shared catchment cells (cannibalisation), and turn cells only it covered into growth areas. Expect all three; test in Task 3.
2. **The airport lounge.** Expect it in the data and on the map, labelled **NOT SCORED**, never PROTECT/HOLD/SHRINK, and left out of network counts and growth logic as a catchment owner. Test in Task 4.
3. **Thin premium markets** (al-dhafra, al-falah: < 10 premium salons). Their capture is unreliable: expect a neutral capture score (0.5) and low confidence, never PROTECT from capture alone. Test in Task 4.
4. **A lounge with no substitutes, or substitutes with no ratings.** Capture 1.0 (thin-market rule applies); rating gap neutral. Never NaN. Test in Tasks 3-4.
5. **Switching levels.** Every combination of travel time (10/15/20) x coverage (50/60/70%) x worker share (low/medium/high) must build without error and in under ~2 s (the app reruns on every click). Test in Task 3 (correctness) and Task 8 (AppTest timing).
6. **Stale processed data.** A `data/processed/` built by the old pipeline must be regenerated, not crash the app: bump `PIPELINE_VERSION`. Test in Task 5.

---

## File structure

```
src/market.py                 # NEW: women_15plus, residential_share, market_women, premium_substitutes,
                              #      coverage_k, capture_by_coverage, recall_multiplier, excluded_reason
src/data_v3.py                # NEW: load the committed v3 files into typed objects (one place)
src/models.py                 # Lounge, Cell, LoungeFeatures, Area, Decision, AreaDecision, Explanation...
src/features/build.py         # REWRITE: build(data, levels, closed) -> (lounge features, areas)
src/model/rubric.py           # REWRITE: four new signals, anchors with reasons, NOT SCORED
src/model/opportunity.py      # REWRITE: growth areas on population and distance
src/model/run.py              # writes data/processed/baseline/*.json; PIPELINE_VERSION bump
src/scenario/*                # REWRITE: levels + closed lounges; diff
src/explain.py                # new glossary, facts, topics, templates; cache regenerated
src/webapp/*                  # map (UAE view, catchment polygons, areas, substitutes), pages, editor
scripts/*.py                  # import the maths from src/market.py (no duplicates)
notebooks/decisions.ipynb     # NEW: calibration of the rubric anchors and the area rule (Task 4)
DELETE: data/seed/{branches,communities,competitors}.csv, src/acquire/*, scripts/fetch_competitors.py,
        and their tests
```

---

### Task 1: Move the market-model maths into `src/market.py`

**Why:** the app must not import from `scripts/`. One copy of each function, tested once.

**Files:** Create `src/market.py`, `tests/test_market.py`. Modify `scripts/build_cells.py`, `scripts/fetch_salons.py` (import from `src.market`, delete the moved bodies), the four notebooks' imports, `tests/scripts/test_cells.py`, `tests/scripts/test_salons.py` (move the pure-function tests to `tests/test_market.py`; keep only script-specific tests: caching, circles, tagging).

**Interfaces (moved unchanged):** `residential_share`, `market_women`, `women_15plus(cells, emirates, worker_share)`, `premium_substitutes(candidates, k, min_rating, price_levels)`, `coverage_k(substitutes, share)`, `capture(lounge_reviews, substitutes)`, `capture_by_coverage(lounge_reviews, premium, coverage, multiplier) -> (capture, k)`, `recall_multiplier(full_share, recall)`, `excluded_reason(row)`, `MALE_NAME`, `SALON_TYPES`.

- [ ] **Step 1:** Create `tests/test_market.py` by moving the pure-function tests (block-sum stays with the script). Run it. Expected: FAIL (`src.market` missing).
- [ ] **Step 2:** Create `src/market.py` with the function bodies moved verbatim; in the scripts replace them with `from src.market import ...`. Run `just test`. Expected: all pass.
- [ ] **Step 3:** Re-run the four notebooks (`jupyter nbconvert --execute --inplace`); expect no errors and unchanged numbers.
- [ ] **Step 4:** Commit and push.

### Task 2: Load the v3 data in one place

**Files:** Create `src/data_v3.py`, `tests/test_data_v3.py`. Modify `src/models.py` (add `Lounge`, `Cell`; keep old models until Task 9), `src/config.py` (`v3_dir = seed_dir / "v3"`).

**Interfaces:**
```python
@dataclass(frozen=True)
class V3:
    lounges: list[Lounge]            # branches.csv
    cells: pd.DataFrame              # cells.csv, indexed by cell_id
    emirates: pd.DataFrame           # emirates.csv, indexed by emirate
    catchment: pd.DataFrame          # catchment_cells.csv (cell_id, level, branch_id)
    salons: pd.DataFrame             # salons.csv
    candidates: pd.DataFrame         # lounge_candidates.csv
    saturation: pd.DataFrame         # lounge_search_saturation.csv, indexed by branch_id
    polygons: dict[tuple[str, int], dict]   # (branch_id, minutes) -> GeoJSON geometry (lounge_isochrones)

def load_v3(settings: Settings | None = None) -> V3: ...   # cached with functools.lru_cache in the app
```
`Lounge`: `branch_id, title, name, emirate, lat, lng, place_id, rating, review_count, address`.

- [ ] **Step 1: Failing test:** `load_v3()` returns 24 lounges, 2,373 cells, the three catchment levels, and a polygon for every lounge at 10/15/20/30/40 min; `cells` has no NaN in `adults`.
- [ ] **Step 2:** Implement. Run. Expected: PASS. Commit and push.

### Task 3: Lounge features and growth areas for any assumption levels

**Files:** Rewrite `src/features/build.py`. Modify `src/models.py`. Test: `tests/features/test_build_v3.py` (the old `test_build.py` / `test_assign.py` are deleted in Task 9).

**Interfaces:**
```python
@dataclass(frozen=True)
class Levels:                       # names, not values: values come from baseline.yaml
    travel: str = "medium"          # travel_time_minutes key
    coverage: str = "medium"        # competitor_coverage key
    worker_share: str = "medium"    # worker_housing_female_share key

class LoungeFeatures(BaseModel):
    branch_id: str; name: str; emirate: str; lat: float; lng: float
    rating: float | None; review_count: int
    catchment_women: float          # women 15+ in its catchment cells
    catchment_cells: int
    shared_share: float             # share of those women in cells another (open) lounge also reaches
    capture: float                  # capture_by_coverage
    substitutes_k: int
    recall_multiplier: float
    premium_pool: int               # premium salons in its catchment
    thin_premium_market: bool       # premium_pool < THIN_MARKET (10)
    substitutes_median_rating: float | None
    rating_gap: float | None        # rating - substitutes_median_rating
    est_customers: float            # capture x catchment_women (0 if not scored)
    headroom: float
    not_scored: bool                # the airport lounge

class Area(BaseModel):              # growth candidate
    area_id: str; name: str; emirate: str; lat: float; lng: float
    women: float; cells: int; worker_share: float
    cell_ids: list[str]             # for the map and the closed-lounge test
    nearest_lounge_id: str; nearest_lounge_km: float   # straight-line, among OPEN lounges

def build(v3: V3, assumptions: BaselineAssumptions, levels: Levels = Levels(),
          closed: frozenset[str] = frozenset()) -> tuple[list[LoungeFeatures], list[Area]]: ...
```
**Rules:** women per cell = `women_15plus(cells, emirates, worker_share[level])`. Catchment = `catchment_cells` at `levels.travel`, open lounges only. `shared_share` counts only open lounges. Candidates exclude closed lounges. Growth areas = populated cells in **no** open lounge's catchment, grouped by `(name, emirate)` (the OSM name already on each cell); `area_id` = slug of name + emirate; lat/lng = women-weighted centre; `NOT_SCORED = {"zayed-international-airport"}` (its catchment still counts as "reached" for growth areas, because the lounge exists).

- [ ] **Step 1: Write the failing tests** (small synthetic V3 fixtures, no files):

```python
def test_shared_share_counts_only_open_lounges(tiny_v3):
    f, _ = build(tiny_v3, ASSUMPTIONS)                     # a and b share cell c2
    assert by_id(f)["a"].shared_share == pytest.approx(women("c2") / (women("c1") + women("c2")))
    f, _ = build(tiny_v3, ASSUMPTIONS, closed=frozenset({"b"}))
    assert by_id(f)["a"].shared_share == 0
    assert "b" not in by_id(f)

def test_closed_lounge_leaves_substitute_sets(tiny_v3):    # b is a premium candidate of a
    open_cap = by_id(build(tiny_v3, ASSUMPTIONS)[0])["a"].capture
    closed_cap = by_id(build(tiny_v3, ASSUMPTIONS, closed=frozenset({"b"}))[0])["a"].capture
    assert closed_cap > open_cap

def test_cells_only_a_closed_lounge_reached_become_growth_areas(tiny_v3):
    _, areas = build(tiny_v3, ASSUMPTIONS, closed=frozenset({"b"}))
    assert "c3" in {c for a in areas for c in a.cell_ids}   # c3 was only b's

def test_no_substitutes_and_no_ratings_never_nan(tiny_v3_empty):
    f = build(tiny_v3_empty, ASSUMPTIONS)[0][0]
    assert f.capture == 1.0 and f.thin_premium_market and f.rating_gap is None

def test_every_level_combination_builds(real_v3):       # Review Focus 5
    for t, c, w in itertools.product(["low", "medium", "high"], repeat=3):
        f, a = build(real_v3, ASSUMPTIONS, Levels(t, c, w))
        assert len(f) == 24 and all(x.catchment_women > 0 for x in f)
```
- [ ] **Step 2:** Run. Expected: FAIL. Implement `build`. Run. Expected: PASS.
- [ ] **Step 3:** Check against `competitors.ipynb` at medium levels: catchment women, capture and k per lounge match the notebook's table exactly. Commit and push.

### Task 4: The scorecard and growth rule, calibrated (user reviews the anchors)

**Files:** Rewrite `src/model/rubric.py`, `src/model/opportunity.py`. Create `notebooks/decisions.ipynb`. Test: `tests/model/test_rubric.py`, `tests/model/test_opportunity.py` (rewritten).

**Draft signals and anchors** (fixed scales, so a lounge's score doesn't move when a sibling changes; computed 2026-10-09 at medium levels):

| Signal | Field | 0 at | 1 at | Why (data at medium levels) |
|---|---|---|---|---|
| Demand | `catchment_women` | 0 | 200,000 | Range 23k-272k, median 105k; the four big Dubai lounges saturate |
| Cannibalisation | `shared_share` | 100% | 0% | Already a share; Abu Dhabi city lounges sit at 85-100% shared |
| Capture | `capture` | 0 | 15% | Median 5.8%; 15% ≈ the best reliable lounges (al-taif-mall 14%). **Thin markets score 0.5** (neutral) |
| Relative rating | `rating_gap` | −0.3★ | +0.3★ | Gap range −0.2 to +0.3, median −0.1: most lounges rate slightly below their substitutes |

Preview with these anchors, the thin-market rule and the airport excluded: **2 PROTECT** (al-ain, al-taif-mall), **13 HOLD**, **8 SHRINK** (al-barsha, al-maqta, shahama, khaleej-al-arabi, noya-plaza, mohammed-bin-zayed-city, delma, westyas), **1 NOT SCORED**. Without the thin-market rule al-falah would be PROTECT on capture alone (54% of a 6-salon pool). Expect the user to question al-barsha as SHRINK: it's Dubai's biggest catchment but captures 0.8% of a crowded premium market and shares 86% of its catchment with other lounges. **The user reviews this before it's frozen** (decision D10's pattern: Claude proposes anchors with reasons, the user can veto).

**Growth rule** (population and distance only; competitors unknown outside catchments):
- **GROW:** ≥ `GROW_MIN_WOMEN` (20,000) women 15+ and worker housing < 50% of adults.
- **WATCH:** 5,000-20,000 women, or ≥ 20,000 but mostly worker housing.
- **SKIP:** under 5,000 women.
Every area is, by construction, beyond a 15-min drive of every open lounge; its straight-line distance to the nearest one is shown. Limitation, stated on every area: *no competitor data; saturation unknown*.

- [ ] **Step 1: Failing tests:** scores on the anchors (0 at the 0-anchor, 1 at the 1-anchor, clipped); thin market → capture score 0.5 and confidence "low"; NOT SCORED lounge → action `"NOT SCORED"`, excluded from counts; growth thresholds and the worker-housing cap; the airport's catchment still blocks growth areas.
- [ ] **Step 2:** Implement (`SIGNALS` keep the `Signal(name, field, label, worst, best, why)` shape; `Decision.action` gains `"NOT SCORED"`; `AreaDecision` replaces `OpportunityDecision`). Run. Expected: PASS.
- [ ] **Step 3: Calibration notebook** `notebooks/decisions.ipynb`: signal distributions with the anchors drawn on; composite and action per lounge at medium levels; how actions move across all 27 level combinations (a lounge that flips often gets "low confidence"); growth areas ranked, mapped (`scripts/spot_maps.py`), with counts by emirate; two examples at the bottom (as in the other notebooks).
- [ ] **Step 4: Stop and show the user** the anchors, the actions and the growth list. Adjust on their call. Commit and push.

### Task 5: Pipeline wiring

**Files:** Modify `src/model/run.py`, `src/scenario/baseline.py`, `src/webapp/data.py`, `justfile`.

- `src/scenario/baseline.py: main()` = `load_v3` → `build` at medium levels → rubric + growth rule → write `data/processed/baseline/{lounge_features,decisions,areas,area_decisions,run_meta}.json`. No acquire stage.
- `PIPELINE_VERSION = 4` so an old `data/processed/` regenerates (Review Focus 6).
- `BaselineData` holds lounge features, decisions, areas, area decisions, and the `V3` handle (for polygons and substitutes on the pages); `data_sources` names the real sources.
- `just all` runs the new baseline; `just scenario` is removed (Task 6 makes scenarios in-memory only).

- [ ] **Step 1: Failing test:** a `run_meta.json` with `pipeline_version: 3` triggers regeneration; the baseline has 24 decisions, one NOT SCORED.
- [ ] **Step 2:** Implement. `just all`, `just test`. Commit and push.

### Task 6: Scenarios: switch levels, close lounges

**Files:** Rewrite `src/scenario/models.py` (`ScenarioAssumptions` = `Levels` + `search_recall: float | None`; `ScenarioOverrides` = `closed: list[str]`), `src/scenario/run.py`, `src/scenario/diff.py`; delete `src/scenario/apply.py`, `load.py` and the CLI. Tests: rewrite `tests/scenario/*`.

**Interfaces:** `run_scenario(scenario, v3, assumptions) -> ScenarioRun` (in memory; no files). `ScenarioDiff`: per lounge, old/new action, composite and the four signals; per growth area, appeared / disappeared / action changed.

- [ ] **Step 1: Failing tests:** closing al-barsha changes jumeirah-park's and city-walk's shared share and capture (they shared cells and it was in their substitute sets) and creates no growth area in Dubai's core (others still reach those cells); switching travel to `high` raises every catchment; an unknown lounge id in `closed` raises a clear error; the baseline scenario diffs to nothing.
- [ ] **Step 2:** Implement. Run. Commit and push.

### Task 7: Explanations

**Files:** Modify `src/explain.py`, `tests/test_explain.py`; regenerate `data/explanations/cache.json`.

- New `GLOSSARY` for every field shown (catchment women, cells, shared share, capture, substitutes k, recall multiplier, premium pool, thin market, rating gap, substitutes' median rating, estimated customers, headroom; area women, worker share, nearest lounge km), each with unit and meaning taken from `SOURCES.md` "Market model".
- `TOPICS`: branch → demand / cannibalisation / capture / quality; area → reach / size / worker_housing / data_gap; network → shrink / grow / protect / confidence / data_gaps.
- `PROMPT_VERSION = "v4"` (old cache entries no longer match). The grounding check (`verify`) is unchanged; the facts it checks change.
- NOT SCORED lounges get a fixed template ("Not scored: serves travellers..."), never an LLM call.

- [ ] **Step 1:** Update the tests for the new facts and topics (template explanations must pass `verify` for every lounge and area). Run. Expected: FAIL, then implement, PASS.
- [ ] **Step 2: Ask the user**, then run `just explain` (needs `ANTHROPIC_API_KEY`; ~24 lounges + growth areas + network). Report how many pass grounding. Commit the cache and push.

### Task 8: The app

**Files:** Modify `src/webapp/map.py`, `pages/overview.py`, `pages/branch.py`, `pages/area.py`, `views.py`, `scenario_editor.py`, `nav.py`, `streamlit_app.py`. Tests: `tests/webapp/*` rewritten (AppTest smoke for every page, map layer specs).

- **Map:** opens on the UAE (all five emirates); lounges coloured by action (NOT SCORED grey) with flags; selecting a lounge draws its 15-min polygon (from `V3.polygons`, current travel level) and its catchment cells shaded by women; growth areas as cell squares coloured GROW / WATCH / SKIP; optional layer: the selected lounge's premium substitutes, sized by reviews.
- **Overview:** executive summary (pyramid); map; side panel with layer toggles and a legend that states every threshold; the what-if panel: three level selectors (travel time, coverage, worker-housing share), a recall input, and "close lounges" multiselect; a "what changed" summary from `ScenarioDiff`.
- **Branch page:** decision and pyramid; the four signals on their scales; catchment map; the substitutes table (name, reviews, rating, premium because…); shared catchment with which lounges; caveats (thin market, NOT SCORED, Mirdif's undetected labour camps).
- **Area page:** GROW/WATCH/SKIP with the rule; women, worker share, nearest lounge; the cell map; the "no competitor data here" caveat.
- **How it works:** a page or expander rendering `SOURCES.md` "Market model" and the README assumptions table, so reviewers see every assumption in the app.

- [ ] **Step 1:** Update `tests/webapp/*` (AppTest: each page loads with no exception at medium levels and with a scenario closing two lounges; a level switch completes in < 2 s). Run. Expected: FAIL.
- [ ] **Step 2:** Implement page by page; run the app (`just app`) and click through every page and the what-if panel in a browser; fix what's wrong. Expected: tests PASS.
- [ ] **Step 3:** Commit and push.

### Task 9: Remove the old data and code; docs

**Files:** Delete `data/seed/{branches,communities,competitors}.csv`, `src/acquire/`, `scripts/fetch_competitors.py`, `data/scenarios/example-perturbations.yaml`, old models (`Branch`, `Community`, `CommunityAssignment`, `Competitor`, `BranchFeatures`, `CommunityFeatures`, `OpportunityDecision`, `NetworkStats` if unused), and their tests (`tests/acquire/`, `tests/features/test_assign.py`, `test_build.py`, `tests/test_seed_data.py`, etc.). Modify `README.md`, `CONTEXT.md`, `docs/remaining.md`.

- **README:** rewrite "Run it", "Using the app", "What it currently says", "How it decides", "Data" and "Repo map" for the new model (keep the reviewer-first tone and the assumptions table at the bottom); remove the "live app still runs on the old data" note.
- **CONTEXT.md:** add *Cell*, *Catchment (drive-time)*, *Premium substitute*, *Capture*, *Coverage*, *Search recall*, *Growth area*; retire *Community* as the unit.
- [ ] **Step 1:** Delete; `grep -rn "communities.csv\|competitors.csv\|src.acquire\|BranchFeatures\|OpportunityDecision" src tests scripts notebooks` returns nothing; `just test` passes.
- [ ] **Step 2:** Docs. Commit and push.

### Task 10: Ship

- [ ] **Step 1:** `just test`; run every notebook; run the app locally and click through once more.
- [ ] **Step 2: Ask the user** to merge `data-refresh` into `main` (the live deploy). After merge, check that Streamlit Community Cloud redeployed and the overview shows the UAE network.

---

## Not in this plan (deliberate)

- Moving or adding a lounge in what-ifs (needs live Mapbox/Google calls).
- Competitor data for growth areas (outside catchments); a full sweep to replace `search_recall`.
- Distance decay (Huff), rush-hour catchments, Bedashing's real price level.
