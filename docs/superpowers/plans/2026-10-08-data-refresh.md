# Data Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hand-curated seed (4 of 9 Dubai "branches" don't exist) with data fetched once from real sources and committed: Bedashing's lounges, neighbourhoods with an approximate market size, travel-time reach, and each lounge's top premium substitutes (competitors) inside its catchment, with Google ratings and review counts. Together these feed the market model below.

**Architecture:** One script per stage under `scripts/`, each reading the previous stage's committed output from `data/seed/v3/` and writing its own. Each script is run once by hand, its output is vetted in a notebook, then committed. The pipeline under `src/` and the app are **not** touched here; switching them to `data/seed/v3/` is a follow-up plan, so the live app and the existing 115 tests keep working throughout.

**Market model (agreed 2026-10-08; built in the integration plan, data for it built here):**
- **Unit:** a ~2 km grid **cell** (0.02°), not an official neighbourhood: OSM neighbourhoods are patchy outside Abu Dhabi, and the model never needed official boundaries. Cells carry an OSM name for display. (Changed 2026-10-08; "neighbourhood" below means cell.)
- **Market size per cell** `market(n)` = women 15+ (Task 2): WorldPop adults, with the sex split redone because WorldPop applies one national ratio (33.6%) everywhere. Adults in OSM industrial land use (worker housing) get `worker_housing_female_share` (calibrated on Dubai labour-camp communities: 5.5%); every other cell gets the share that keeps each emirate's female total. Only *relative* accuracy matters; the one thing it must get right is the worker-housing skew (the bug that inflated jumeirah-park).
- **Catchment:** a lounge's catchment = the cells inside its drive-time isochrone at `travel_time_minutes` (medium 15 min). **Catchment market** = the women 15+ in those cells.
- **Revised 2026-10-09: k is now coverage-based** — substitutes are the most-reviewed premium salons holding `competitor_coverage` (60%; 50/70) of the catchment's premium reviews, and their reviews are scaled by a recall multiplier (`search_recall` 0.66, calibrated on the Al Barsha probe; `lounge_search_saturation.csv`). A fixed k covered 22-66% of the market depending on the catchment. The fixed-k text below is historical.
- **Competitors = premium substitutes, top k (revised 2026-10-08).** For each lounge, candidates are women's beauty, hair and nail salons inside its catchment (men-only and closed excluded). A candidate is a **premium substitute** if Google's price level is `comparable_price_levels` (expensive, very expensive) or, where Google has no price (~80% of salons), if its reviews are at least the catchment's median and its rating is at least `premium_min_rating` (4.3). Keep the **top k by review count**, k = `competitor_k` (**20**; 10 and 30 as sensitivity). **Other Bedashing lounges in the catchment count as substitutes**, so lounges with overlapping catchments split their shared demand (cannibalisation).
- **Capture** = lounge reviews ÷ (lounge reviews + the k substitutes' reviews). **Estimated customers** = capture x catchment market; **headroom** = catchment market minus estimated customers. Name it "share among premium substitutes", not market penetration.
- **Known bias, measured:** reviews are concentrated in thin markets and spread out in dense ones (probe, 2026-10-08: the top 10 salons hold 82% of reviews around Al Dhafra but 24% around Al Barsha). So a fixed k leaves out more of the market in dense cities, and capture is overstated more there than in small towns. The k = 10/20/30 sensitivity shows how much; the notebook reports, per lounge, what share of all candidate reviews the k substitutes cover.
- **Rejected (2026-10-08):** splitting each cell's women among every salon that reaches it. More exact, but it needs every salon in the 30-min zones: ~2,100 Places calls (~$15-60) against 72-144 for this design. The cell isochrones from Task 3 stay committed for that later upgrade.
- **Growth candidates:** populated cells outside every lounge's catchment (all cells are in `cells.csv`, so this costs nothing extra).
- **Stated limitations:** review counts are lifetime totals (older salons are favoured; see `SOURCES.md`); chains likely push for more reviews than independents, inflating Bedashing's share; no distance decay inside the travel time (every reachable salon competes equally; a Huff model is the later upgrade, the three travel-time levels are the sensitivity check); home-service salons are invisible; income and nationality mix are ignored; mall lounges draw beyond their drive-time zone.
- **Price segment:** Bedashing's own level is an **assumption** (`bedashing_price_level: expensive` in `baseline.yaml`; Google has no price for its lounges; to be revisited from its own menu). Google's `priceLevel` is crowd-sourced spend per person in coarse brackets, and only ~20% of salons have it (probe, 2026-10-08), so where it's missing the premium stand-in (reviews and rating, above) decides. No imputation.
- **Excluded from the market model:** `zayed-international-airport` (serves travellers, not a neighbourhood). Kept in the data, flagged.
- **Optional, later:** a market value in AED = women × visits per year × average spend, as low/medium/high assumptions in `baseline.yaml`. It scales every number equally and changes no rankings, so it's not needed for decisions.

**Tech Stack:** Python 3.11+, stdlib `urllib` for HTTP, Google Places API (New) Text Search, openrouteservice isochrones (Task 3), WorldPop rasters (Task 2), `shapely` for geometry, a raster reader for WorldPop (Task 2), pandas and matplotlib in notebooks.

**Spec:** this conversation's brief (2026-10-08): "get branches, get all neighbourhoods, compute catchment, get competitors within the catchment, get ratings info for all branches and competitors, fetch once and check it in." Background: `docs/remaining.md`, `README.md` (Data section).

## Global Constraints

- **Fetch once, commit the output.** No script runs in the app or the pipeline. Re-running a script must not re-bill: skip any stage whose output file exists unless `--force` is passed.
- **Scope (changed 2026-10-08): all 24 UAE lounges**, every emirate; WorldPop (Task 2) covers all of them with one method, so an emirate drops out of results only if that fails. Original line: **Dubai and Abu Dhabi emirates** (20 of the 24 lounges; Abu Dhabi includes Al Ain and Al Dhafra). Sharjah, Ras Al Khaimah and Fujairah lounges stay in `lounges.json` but are filtered out, because we have no population data for them. Revisit only if Task 2 finds population for them at no extra effort.
- **Google Places budget:** every call that asks for `rating` bills at the Enterprise tier, with 1,000 free calls a month at $35 per 1,000 after that. Each script has a `MAX_CALLS` hard stop. Before Task 4 runs, set a per-day request quota on the Places API in the Cloud Console (project `driven-copilot-364002`) as the backstop.
- **Google terms:** only `place_id` may be stored indefinitely; ratings and coordinates should be refreshed within 30 days. Acceptable for a case study, but state it in `data/seed/v3/SOURCES.md`.
- **Secrets:** `GOOGLE_MAPS_API_KEY` (and any isochrone key) live in `.env` only, are read via `src/config.py`, and are never printed.
- **Every committed file gets a provenance row** in `data/seed/v3/SOURCES.md`: source URL or endpoint, fetch date, script, row count, known gaps.
- **No new dependency for something a few lines can do.** Expected additions, all in the `notebook` extra: `shapely` (Task 3) and a raster reader for WorldPop (Task 2).
- **openrouteservice quota:** about 500 isochrone requests a day; Task 3 needs one day's worth at most. Cache every response.

## Review Focus

1. **A lounge with no Google match.** Expect `place_id` empty and the row kept and flagged, not silently matched to the nearest random salon. Tested in Task 1 (`best_match` returns `None`).
2. **Bedashing's own listings among the candidates.** The search returns them too. Expect each lounge excluded from its **own** substitute set but kept (with `is_bedashing` and `branch_id`) in other lounges' sets. Test in Task 4.
3. **Fewer than k premium substitutes** (Al Dhafra has ~33 women's salons in all). Expect the set to hold however many qualify, its size reported, and capture computed on that; a lounge with **zero** substitutes gets capture 1.0, flagged, never a crash. Test in Task 4.
4. **A salon in two lounges' catchments.** Expect it stored once in `salons.csv`, with a row per lounge in `lounge_candidates.csv`, and counted in both lounges' sets. Test in Task 4.
5. **Re-running a script after a crash halfway through.** Expect no re-billing: each lounge's query responses are cached in `data/raw/places_cache/` (gitignored), and the CSVs are written only at the end. Test in Task 4.
6. **Missing review count or rating** on a candidate. Expect review count 0 (never in the top k by reviews) and no premium stand-in without a rating; never NaN in capture. Test in Task 4.
---

## File structure

```
data/seed/lounges.json                 # store-locator snapshot (already saved, 24 lounges)
data/seed/v3/branches.csv              # Task 1: 24 lounges + Google place, rating, reviews
data/seed/v3/cells.csv                 # Task 2: ~2 km cells: adults, worker-housing adults, name, emirate
data/seed/v3/emirates.csv              # Task 2: emirate totals (to rebalance the female share)
data/seed/v3/dubai_community_gender.csv # Task 2: DSC 2022 sex split, 23 Dubai communities (calibration)
data/seed/v3/lounge_isochrones.geojson # Task 3: per lounge, catchment levels + 2x competitor bounds
data/seed/v3/cell_isochrones.geojson   # Task 3: per catchment cell x level
data/seed/v3/catchment_cells.csv       # Task 3: cell x level x lounge whose catchment holds it
data/seed/v3/salons.csv                # Task 4: unique candidate salons (type, rating, reviews, price, Bedashing flag, excluded reason)
data/seed/v3/lounge_candidates.csv     # Task 4: lounge x candidate salon inside its 15-min catchment
data/seed/v3/SOURCES.md                # provenance for every file above
scripts/places.py                      # shared Google Places client (from scripts/fetch_places.py)
scripts/fetch_branches.py              # Task 1
scripts/build_cells.py                 # Task 2
scripts/fetch_isochrones.py           # Task 3
scripts/fetch_salons.py                # Task 4
tests/scripts/test_places.py           # Task 1 helpers: name filter, matching
tests/scripts/test_cells.py            # Task 2: block sums, female-share rebalancing
tests/scripts/test_isochrones.py       # Task 3: reaches
tests/scripts/test_salons.py           # Task 4: exclusions, Bedashing tagging, premium set, capture, cache
notebooks/branches.ipynb               # vets Task 1 (exists; extend)
notebooks/market_size.ipynb            # Task 2: model structure, assumptions, vetting
notebooks/reach.ipynb                  # vets Task 3
notebooks/competitors.ipynb            # Task 4: substitutes, capture at k = 10/20/30
```

`scripts/fetch_places.py` (written earlier, partially run: about 29 billed calls, no output) is split into `scripts/places.py` (client and helpers) and `scripts/fetch_branches.py`. Its competitor half is replaced by Task 4.

**Notebooks:** the user edits `.ipynb` files directly in their own Jupyter. Before an agent edits a notebook, ask the user to save and close it, or hand them the cells to paste in.

---

### Task 0: Research travel time (no code) — DONE 2026-10-08

**Files:** Create `data/seed/v3/SOURCES.md` (the first section: "Catchment travel time").

- [x] **Step 1:** Search for published evidence on how far people travel to a beauty or nail salon: consumer surveys, retail trade-area studies, any GCC or UAE studies. Record 2 or 3 sources, each with the number it supports (minutes or km, drive or walk).
- [x] **Done 2026-10-08:** low/medium/high = 10/15/20 min in `data/scenarios/baseline.yaml` (`travel_time_minutes`), evidence in `SOURCES.md`. Superseded steps below kept for history.
- [x] **Step 2:** Pick **one** drive-time threshold (expected range 10–20 min) and, if the evidence supports it, a separate walk threshold for mall branches. Write the choice and the reason in `SOURCES.md`. This is a judgement call, like the existing thresholds, and gets stated rather than tuned.
- [x] **Step 3:** Ask the user to confirm the threshold before Task 3 runs. It decides how big every catchment is, and therefore how many Places calls Task 4 makes.

### Task 1: Branches (lounges + Google rating) — DONE 2026-10-08, 24/24 matched; see SOURCES.md

**Files:**
- Create: `scripts/places.py`, `scripts/fetch_branches.py`, `tests/scripts/__init__.py`, `tests/scripts/test_places.py`
- Delete: `scripts/fetch_places.py`
- Output: `data/seed/v3/branches.csv`

**Interfaces:**
- Produces (`scripts/places.py`):
  - `search(body: dict, *, paged: bool = False) -> dict`: POST to `places:searchText` with the module's `FIELDS` mask. Counts calls against `MAX_CALLS` and raises `SystemExit` with Google's error body on HTTP errors.
  - `is_bedashing(place: dict) -> bool`
  - `best_match(places: list[dict], lat: float, lng: float, max_km: float = 1.0) -> dict | None`: the nearest Bedashing listing within `max_km`, otherwise `None`.
  - `to_row(place: dict) -> dict`: keys `place_id, name, address, lat, lng, rating, review_count, status, primary_type`.
  - `km(lat1, lng1, lat2, lng2) -> float`: re-export `src.features.assign.haversine_km`; don't re-implement it.
- `branches.csv` columns: `branch_id` (the locator `slug`), `title`, `emirate`, `locator_address`, `locator_lat`, `locator_lng`, `place_id`, `name`, `address`, `lat`, `lng`, `pin_offset_km`, `rating`, `review_count`, `status`, `fetched_at`.

- [x] **Step 1: Write the failing tests**

```python
# tests/scripts/test_places.py
from scripts.places import best_match, is_bedashing

def place(name, lat, lng):
    return {"id": name, "displayName": {"text": name},
            "location": {"latitude": lat, "longitude": lng}}

def test_is_bedashing_any_case():
    assert is_bedashing(place("BEDASHING Beauty Lounge Delma", 0, 0))
    assert not is_bedashing(place("Pink Madi Beauty Salon", 0, 0))

def test_best_match_picks_nearest_bedashing():
    near = place("Bedashing Beauty Lounge Al Barsha", 25.1131, 55.2156)
    far = place("Bedashing Beauty Lounge City Walk", 25.2020, 55.2638)
    rival = place("Leilani Beauty Lounge", 25.1137, 55.2146)
    assert best_match([rival, far, near], 25.1137, 55.2146) is near

def test_best_match_none_when_only_far_or_rivals():
    far = place("Bedashing Beauty Lounge City Walk", 25.2020, 55.2638)
    assert best_match([far, place("Some Salon", 25.1137, 55.2146)], 25.1137, 55.2146) is None
```

- [x] **Step 2:** Run `uv run --extra dev pytest tests/scripts -v`. Expected: FAIL (`scripts.places` doesn't exist).
- [x] **Step 3:** Move `search`, `km`, `row` and `circle` from `scripts/fetch_places.py` into `scripts/places.py`, and add `is_bedashing` and `best_match`. Write `fetch_branches.py`: load `data/seed/lounges.json`, keep the Dubai and Abu Dhabi lounges (`state` in {"Dubai", "Abu Dhabi"}; normalise the empty `state` on City Walk to Dubai using `city`), `html.unescape` the text fields, run one search `"Bedashing Beauty Lounge {title}"` with a 2 km `locationBias` per lounge, and write the CSV. `MAX_CALLS = 30`. Skip if the output exists and `--force` isn't set. Delete `scripts/fetch_places.py`.
- [x] **Step 4:** Run the tests. Expected: PASS.
- [x] **Step 5:** Ask the user before running (20 billed calls): `uv run python scripts/fetch_branches.py`.
- [x] **Step 6: Vet** in `notebooks/branches.ipynb`, replacing the old-seed checks with: unmatched lounges; `pin_offset_km` > 0.3; status not `OPERATIONAL`; rating and review-count distribution; Dubai lounges vs. old `data/seed/branches.csv` (which old branches don't exist). Write the findings in a markdown cell.
- [x] **Step 7:** Add a `branches.csv` row to `SOURCES.md`, then commit `scripts/places.py scripts/fetch_branches.py tests/scripts data/seed/lounges.json data/seed/v3/branches.csv data/seed/v3/SOURCES.md notebooks/branches.ipynb` (plus the deletion of `scripts/fetch_places.py`).

### Task 1b: Review rate: DROPPED 2026-10-08

Considered normalising review counts by age (reviews per year since the first review).
Dropped: Google Maps can't sort reviews oldest-first, so the first review needs a full
scrape of every review (~21k for Bedashing, unaffordable for competitors) and breaks Google's
terms. **Decision:** use raw lifetime `review_count` for lounges and competitors alike, and
state the age caveat (see `SOURCES.md`, "Review counts").

### Task 2: Market size per grid cell — DONE 2026-10-08

**What was found (research, 2026-10-08):**
- **WorldPop 2025 (R2025A, 100 m, constrained, CC BY 4.0)** has female and male rasters by
  5-year age band for the whole UAE. But **every cell is 33.6% female**: one national ratio,
  no local variation. It overstates women in labour camps *and* understates them in residential areas.
- **OSM neighbourhoods are patchy:** Abu Dhabi's level-8 polygons cover 100% of its women; Dubai's
  128 communities 66%; Sharjah's level 8 is whole towns; Fujairah has none. So: a grid.
- **Dubai Statistics Center community figures with sex split** (2022, via citypopulation.de, 23
  communities fetched): labour-camp industrial areas are 0.1-27% female (5.5% weighted by
  population); residential 43-54%; **Al Qusais "Industrial" is residential** (42-48%), so names
  don't identify worker housing.

**Built:** `scripts/build_cells.py` → `cells.csv` (2,373 cells with ≥ 500 adults, 94.4% of UAE
adults: adults, adults in OSM industrial land use, WorldPop women, OSM name), `emirates.csv`
(totals). The female split is **not** baked in: women are recomputed from
`worker_housing_female_share` (low 1% / medium 5.5% / high 15%, `baseline.yaml`), with the
residential share rebalanced per emirate. Tests: `tests/scripts/test_cells.py`.

- [x] **Step 1:** Sources confirmed (above); raw files in `data/raw/worldpop/`, `data/raw/osm/` (gitignored).
- [x] **Step 2:** `build_cells.py` + tests; `dubai_community_gender.csv` committed as calibration evidence.
- [x] **Step 3: Notebook** `notebooks/market_size.ipynb`: the model structure and every assumption, with its reasons (the user asked for this to live next to the data); WorldPop emirate totals; the flat 33.6% finding; the calibration table; **validation**: modelled female share vs measured for the 21 measured communities located by OSM place points (MAE 0.21 → 0.13; unmapped camps such as DIP and Sonapur are missed); the women per cell map; how much the correction moves women near each lounge (low/medium/high).
- [x] **Step 4:** `SOURCES.md` "Market size" section, README table rows (3, 4, 5, new 13), commit.

### Task 3: Lounge catchments and cell reach (drive-time isochrones) — DONE 2026-10-08

**Changed during execution:** openrouteservice's free key allowed only ~250 isochrones a day (counted per location), so the script moved to the **Mapbox Isochrone API** (`driving-traffic`, typical traffic at `isochrone_depart_at`, weekday 12:00; 2 requests per lounge, 1 per cell). Results: 257 / 542 / 810 catchment cells at 10 / 15 / 20 min; all 120 lounge and 2,430 cell polygons; 30-min search area 8,320 km². Committed polygons are simplified to ~200 m; memberships use the full-detail polygons from the cache. The ORS mentions in the steps below are historical.


**Files:** Create `scripts/fetch_isochrones.py`. Outputs: `lounge_isochrones.geojson`, `cell_isochrones.geojson`, `catchment_cells.csv`.

**Interfaces:**
- Consumes: `branches.csv` (`branch_id`, `lat`, `lng`: Google's pin), `cells.csv` (`cell_id`, `lat`, `lng`), and `travel_time_minutes` from `baseline.yaml`.
- Produces:
  - `lounge_isochrones.geojson`: per lounge, one polygon per range in {10, 15, 20, 30, 40} min (the three catchment levels, plus 2x bounds 30 and 40 for medium and high; 2x low = 20 is already there), properties `branch_id, minutes`.
  - `catchment_cells.csv` columns `cell_id, level, branch_id`: cells whose centre is inside the lounge's catchment polygon at that level.
  - `cell_isochrones.geojson`: per catchment cell (any level), one polygon per catchment level, properties `cell_id, level, minutes`.
  - `reaches(isochrone: Polygon, points: dict[str, tuple[float, float]]) -> list[str]`.

- [x] **Step 1: Key.** openrouteservice isochrones (free key; ~500 requests a day; 5 locations and up to 10 ranges per request). The user creates the key and adds `ORS_API_KEY` to `.env` and `src/config.py`. Cache every response in `data/raw/isochrone_cache/`. Typical traffic only: say so in `SOURCES.md`.
- [x] **Step 2: Write the failing test**

```python
# tests/scripts/test_isochrones.py
from shapely.geometry import Polygon

from scripts.fetch_isochrones import reaches


def test_reaches_returns_points_inside_only():
    square = Polygon([(55.0, 25.0), (55.1, 25.0), (55.1, 25.1), (55.0, 25.1)])
    pts = {"in": (25.05, 55.05), "out": (25.2, 55.2)}   # (lat, lng)
    assert reaches(square, pts) == ["in"]
```
- [x] **Step 3:** Run it. Expected: FAIL. Implement `reaches` (shapely points are `(lng, lat)`). Run again. Expected: PASS.
- [x] **Step 4: Lounge isochrones** (24 lounges ÷ 5 = 5 requests). Compute `catchment_cells.csv`. **Report the count of catchment cells** (at the high level) before Step 5: cell isochrones cost (cells ÷ 5) requests; if that exceeds ~450, ask the user (options: medium level only, or two days of quota).
- [x] **Step 5: Cell isochrones** for every catchment cell, all three levels per request.
- [x] **Step 6: Vet** in `notebooks/catchments.ipynb`: each lounge's catchment polygon and cells on a map; women per catchment at each level (with the worker-housing correction at low/medium/high); lounges sharing cells (cannibalisation); the 30-min competitor bounds (the Task 4 sweep area, in km²); populated cells outside every catchment (growth candidates).
- [x] **Step 7:** `SOURCES.md` row, commit.

### Task 4: Premium substitutes per lounge, with ratings and review counts (revised 2026-10-08) — DONE 2026-10-09

**Result:** 576 Nearby calls (free tier); 4,237 salons, 2,824 candidates, recall 17/20 on the probe tile. Capture (k = 20) runs from ~2% in dense Dubai to 12-14% where Bedashing leads its set (khalifa-city-a, al-ain); al-dhafra and al-falah have too few premium salons to read. During vetting, the men-only filter gained Arabic terms (حلاق, رجال): 93 more excluded, rebuilt from cache at 0 calls. See `notebooks/competitors.ipynb`.


**Why this shape:** see *Market model* (top). A full sweep of every salon in the 30-min zones was
designed, probed and rejected: ~2,100 calls for a split we don't need.

**Probe already done (2026-10-08, 62 calls, cached in `data/raw/places_cache/`):** one ~8 km tile
around Al Barsha (452 salons; 374 women's salons) and one around Al Dhafra (52; 33). Findings:
review concentration (top 10 hold 24% vs 82% of reviews), price coverage (~20% vs ~4%), and that
"beauty salon" also returns barbers, spas, clinics, shops and schools. These feed the notebook.

**Files:**
- Rewrite: `scripts/fetch_salons.py` (the sweep version is replaced)
- Modify: `scripts/places.py` (price fields, done), `data/scenarios/baseline.yaml` + `src/scenario/models.py` (`competitor_k`, `premium_min_rating`, `comparable_price_levels`)
- Test: `tests/scripts/test_salons.py`
- Outputs: `data/seed/v3/salons.csv`, `data/seed/v3/lounge_candidates.csv`

**Interfaces:**
- Consumes: `branches.csv`, the 15-min polygons in `lounge_isochrones.geojson`, and `search`, `to_row`, `is_bedashing` from `scripts/places.py`.
- Produces:
  - `salons.csv`: `place_id, name, address, lat, lng, rating, review_count, status, primary_type, price_level, price_low_aed, price_high_aed, is_bedashing, branch_id, excluded_reason, fetched_at`. One row per salon.
  - `lounge_candidates.csv`: `branch_id, place_id`, every non-excluded candidate inside the lounge's 15-min polygon (including other Bedashing lounges, excluding the lounge itself). **Selection is not baked in:** the top-k premium set is computed from these with the `baseline.yaml` values, so k = 10/20/30 costs nothing.
  - Helpers: `fetch_lounge(branch, polygon, cache_dir) -> list[dict]`, `excluded_reason(row) -> str` (`men-only`, `not-operational`, `not-a-salon`, or ""), `tag_bedashing(rows, branches)`, `dedupe(rows)`, `premium_substitutes(candidates, k, min_rating, price_levels) -> list[dict]`, `capture(lounge_reviews, substitutes) -> float`.

**Method (revised again 2026-10-09, after validation):** cover the union of the 15-min
catchments with **1.8 km circles** on a gap-free hexagonal grid; each circle gets one **Nearby
Search** for women's-salon *primary* types (`beauty_salon, hair_salon, nail_salon, beautician,
hair_care`), ranked by **popularity**, 20 results. A lounge's candidates are the salons inside its
15-min polygon (other Bedashing lounges added from `branches.csv`). 576 circles = 576 calls,
inside the month's free tier (1.5 km circles would need 770). The first design's per-lounge text
searches (144 calls, done) are merged in from cache.

**Why (validation on the fully swept Al Barsha probe tile, recall of the true top-20 premium
salons by reviews):** one large text search per lounge (the first design): **0-2 / 20**; one large
popularity search: **5 / 20**; text + popularity merged: 5 / 20; **1.5 km popularity circles: 17 /
20** (8/10 at k=10, 23/30 at k=30) for 14 calls. No Google search ranks by review count, and over
a large area its rankings favour keyword matches or its own popularity blend; locally, popularity
finds the most-reviewed salons. `includedPrimaryTypes`, not `includedTypes`: the latter matches any
type and returned hotels, clinics and a car wash.

**Interfaces added:** `circles(area, radius_m) -> list[(lat, lng)]` (gap-free hexagonal cover),
`fetch_circle(lat, lng, radius_m, cache_dir) -> list[dict]` (cached per circle);
`scripts.places.search(..., url=NEARBY_URL)`.

- [x] **Step 1: Write the failing tests** (replace `tests/scripts/test_salons.py`)

```python
from scripts.fetch_salons import capture, dedupe, excluded_reason, premium_substitutes, tag_bedashing


def cand(pid, reviews, rating=4.6, price=""):
    return {"place_id": pid, "review_count": reviews, "rating": rating, "price_level": price}


def test_premium_takes_priced_premium_and_popular_well_rated_unpriced():
    c = [cand("a", 50, price="expensive"),          # priced premium: in, whatever its reviews
         cand("b", 10, price="moderate"),           # priced below: out
         cand("c", 900), cand("d", 300),            # unpriced, popular and well rated: in
         cand("e", 400, rating=4.0),                # popular but rated below 4.3: out
         cand("f", 5)]                              # unpriced, below the median: out
    got = [x["place_id"] for x in premium_substitutes(c, k=20, min_rating=4.3,
                                                      price_levels=["expensive", "very_expensive"])]
    assert got == ["c", "d", "a"]                   # ranked by reviews


def test_premium_caps_at_k():
    c = [cand(str(i), 1000 - i) for i in range(30)]
    assert len(premium_substitutes(c, k=10, min_rating=4.3, price_levels=["expensive"])) == 10


def test_missing_reviews_and_rating_never_premium_stand_in():
    c = [cand("x", None, rating=None), cand("y", 100)]
    assert [x["place_id"] for x in premium_substitutes(c, 20, 4.3, ["expensive"])] == ["y"]


def test_capture_and_no_substitutes():
    assert capture(300, [{"review_count": 600}, {"review_count": 300}]) == 0.25
    assert capture(300, []) == 1.0


def test_excluded_reason():
    ok = {"name": "Pink Lady Salon", "status": "OPERATIONAL", "primary_type": "beauty_salon"}
    assert excluded_reason(ok) == ""
    assert excluded_reason(ok | {"name": "Royal Gents Salon"}) == "men-only"
    assert excluded_reason(ok | {"primary_type": "barber_shop"}) == "men-only"
    assert excluded_reason(ok | {"primary_type": "dental_clinic"}) == "not-a-salon"
    assert excluded_reason(ok | {"status": "CLOSED_PERMANENTLY"}) == "not-operational"


def test_bedashing_kept_and_joined():
    rows = [{"place_id": "g1", "name": "Bedashing Beauty Lounge Delma"},
            {"place_id": "g2", "name": "Pink Madi Beauty Salon"}]
    out = {r["place_id"]: r for r in tag_bedashing(rows, [{"place_id": "g1", "branch_id": "delma"}])}
    assert out["g1"]["is_bedashing"] and out["g1"]["branch_id"] == "delma"
    assert not out["g2"]["is_bedashing"] and not out["g2"]["branch_id"]


def test_dedupe_keeps_one_row_per_place():
    rows = [{"place_id": "a"}, {"place_id": "a"}, {"place_id": "b"}]
    assert [r["place_id"] for r in dedupe(rows)] == ["a", "b"]


def test_cached_lounge_is_not_rebilled(tmp_path, monkeypatch):
    from shapely.geometry import box
    import scripts.fetch_salons as f
    calls = []
    monkeypatch.setattr(f, "search", lambda body, **kw: calls.append(body) or {"places": []})
    branch = {"branch_id": "x", "lat": "25.0", "lng": "55.0"}
    f.fetch_lounge(branch, box(54.9, 24.9, 55.1, 25.1), tmp_path)
    f.fetch_lounge(branch, box(54.9, 24.9, 55.1, 25.1), tmp_path)
    assert len(calls) == 2                          # 2 queries, 1 page each, then cached
```
- [x] **Step 2:** Run them. Expected: FAIL. Rewrite `scripts/fetch_salons.py` (the median for the premium stand-in is over the candidates passed in, i.e. that lounge's catchment). Run again. Expected: PASS.
- [x] **Step 3:** Run it (576 calls, free; `MAX_CALLS = 620`). Report calls used and candidates per lounge. **Commit and push immediately after the fetch** (user request: don't risk losing paid-for data).
- [x] **Step 4: Vet** in `notebooks/competitors.ipynb`: the design and its reasons (from *Market model*); the recall validation above, re-measured on the actual 1.8 km circles against the Al Barsha probe; the probe's concentration and price-coverage numbers; candidates and premium substitutes per lounge; how often the premium stand-in vs. Google's price decided; each lounge's capture at k = 10 / 20 / 30 and the share of all candidate reviews the k substitutes cover (the dense-market bias); Bedashing's rank among its substitutes; other Bedashing lounges appearing in each other's sets; estimated customers and headroom (capture x catchment women).
- [x] **Step 5:** `SOURCES.md` section (sources, competitive-set rules, premium rule, the bias, 30-day terms caveat, home-service limitation); README rows; commit.

### Task 5: Hand-off

- [ ] **Step 1:** Run `just test`. Expected: all existing tests and the new `tests/scripts` pass. The pipeline is untouched.
- [ ] **Step 2:** Add a **"Market model"** section to `data/seed/v3/SOURCES.md` (so the app can show it): the formula, the per-neighbourhood rule, the excluded airport lounge, and every limitation listed under *Market model* at the top of this plan.
- [ ] **Step 3:** Add a "Data refresh (v3)" entry to `docs/remaining.md`: what's now in `data/seed/v3/`, the open findings from each notebook, and the follow-up **integration plan**. That plan must include:
  - Reuse `premium_substitutes` and `capture` from `scripts/fetch_salons.py` (move them into `src/` with their tests).
  - The rubric changes: models gain `emirate` and `place_id`; catchments from `catchment_cells.csv` replace nearest-centroid assignment; the demand signal becomes catchment market and estimated customers; competition becomes capture among the top-k premium substitutes (Google, not OSM), shown at k = 10/20/30; the quality signal is replaced or made relative to nearby salons (ratings only span 4.4-4.9); GROW/WATCH/SKIP uses populated cells outside every catchment; the app map handles every emirate; the airport lounge is excluded from market measures and labelled.
- [ ] **Step 4:** Update the **"Assumptions and evidence"** table at the bottom of `README.md`: move each row's status to *in data* once its data is committed, update values and evidence from the notebooks' findings (e.g. price-level coverage, how many competitors survive the price filter), and add rows for any new assumption.
- [ ] **Step 5:** Commit.

---

## Not in this plan (deliberate)

- Wiring `data/seed/v3/` into `src/` and the app (follow-up plan, once the data is vetted).
- Bedashing's actual price level from its own menu (Phorest booking pages). The `expensive` assumption stands until then.
- A market value in AED (visits × spend). Optional later assumption; it changes no rankings.
- Distance decay inside the travel time (a Huff model). Later upgrade; the three travel-time levels are the sensitivity check for now.
- Service prices from the Phorest booking pages (worth one browser check later; separate task).
- Live traffic or time-of-day travel times.
