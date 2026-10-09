# Data Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hand-curated seed (4 of 9 Dubai "branches" don't exist) with data fetched once from real sources and committed: Bedashing's lounges, neighbourhoods with an approximate market size, travel-time reach, and every salon (Bedashing and competitors) within reach, with Google ratings and review counts. Together these feed the market model below.

**Architecture:** One script per stage under `scripts/`, each reading the previous stage's committed output from `data/seed/v3/` and writing its own. Each script is run once by hand, its output is vetted in a notebook, then committed. The pipeline under `src/` and the app are **not** touched here; switching them to `data/seed/v3/` is a follow-up plan, so the live app and the existing 115 tests keep working throughout.

**Market model (agreed 2026-10-08; built in the integration plan, data for it built here):**
- **Market size per neighbourhood** `market(n)` = female population (WorldPop, Task 2). Only *relative* accuracy matters; precision beyond that doesn't. The one thing it must get right is the sex skew in worker-housing areas (the bug that inflated jumeirah-park).
- **Reach:** salon `s` can serve neighbourhood `n` if `s` lies inside `n`'s drive-time isochrone (Task 3), at each `travel_time_minutes` level.
- **Share out per neighbourhood, never per catchment:** `market(n)` is split among **every** salon that can reach `n`, in proportion to lifetime review count: `share(s, n) = reviews(s) / Σ reviews(s')` over the salons reaching `n`. A lounge's **captured market** = `Σ_n market(n) × share(lounge, n)`. Shares in each neighbourhood sum to 1, so overlapping catchments can't double-count, and two lounges near each other split the same neighbourhoods (cannibalisation falls out of this).
- **A lounge's catchment** = the neighbourhoods it can reach. Decision measures: **share** (lounge reviews ÷ all reviews reaching its neighbourhoods) and **headroom** (catchment market minus captured). Raw captured women largely mirrors review count; don't headline it.
- **Stated limitations:** review counts are lifetime totals (older salons are favoured; see `SOURCES.md`); chains likely push for more reviews than independents, inflating Bedashing's share; no distance decay inside the travel time (every reachable salon competes equally; a Huff model is the later upgrade, the three travel-time levels are the sensitivity check); home-service salons are invisible; income and nationality mix are ignored; mall lounges draw beyond their drive-time zone.
- **Price segment (added 2026-10-08):** only salons in Bedashing's price segment compete for its market. Bedashing's own level is an **assumption** (`bedashing_price_level: expensive` in `baseline.yaml`; to be revisited later, e.g. from its Phorest menu), and only salons at a `comparable_price_levels` level (default `[expensive]`) enter the share formula as competitors. Price comes from Google's `priceLevel` (crowd-sourced spend per person; about half of salons have it). Missing levels are **imputed** (see Task 4); a salon stays in the comparison if its level is still unknown after imputation, so missing data never silently removes competition. Limitation: Google's levels are coarse brackets from user answers, not price lists, and one neighbourhood can mix cheap and premium salons.
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
2. **Bedashing's own listings among the salons.** The search returns them too. Expect them kept (they're salons in the share formula) with `is_bedashing` true and `branch_id` joined from `branches.csv`, never counted as competitors. Test in Task 4.
3. **Dense tiles hitting Google's 60-result cap.** Al Barsha has more than 60 salons within 1 km, so a full tile means "split it", never "that's all of them". Test in Task 4.
4. **A salon reachable from many neighbourhoods.** Expect it stored once in `salons.csv`, with one row per neighbourhood that can reach it in `salon_reach.csv`, not duplicated. Test in Task 4.
5. **Re-running a script after a crash halfway through.** Expect no re-billing for completed lounges or tiles: progress is cached per lounge or tile in `data/raw/places_cache/` (gitignored), and the final CSV is written only at the end. Test in Task 4.
6. **A neighbourhood whose reachable salons all have zero reviews** (or no salons at all). The share formula divides by zero. Expect that neighbourhood's market to stay unallocated (reported as headroom), never NaN or a crash. Test in the integration plan (`apportion`, spec in Task 5).
7. **Shares not adding up.** Expect, per neighbourhood, the shares of all reaching salons to sum to 1, and total captured market ≤ total market. Test in the integration plan (spec in Task 5).
8. **A salon with no price level in a neighbourhood with no priced salons.** Expect the fallback chain (neighbourhood → emirate → unknown) and the salon kept as comparable with `price_level_source = "unknown"`, never dropped. Test in Task 4.

---

## File structure

```
data/seed/lounges.json                 # store-locator snapshot (already saved, 24 lounges)
data/seed/v3/branches.csv              # Task 1: 24 lounges + Google place, rating, reviews
data/seed/v3/neighbourhoods.geojson    # Task 2: polygons + female population (= market size)
data/seed/v3/isochrones.geojson        # Task 3: drive-time polygon per neighbourhood x level
data/seed/v3/lounge_reach.csv          # Task 3: neighbourhood x level x lounge it reaches
data/seed/v3/salons.csv                # Task 4: every salon in the market area (competitors + Bedashing)
data/seed/v3/salon_reach.csv           # Task 4: neighbourhood x level x salon it reaches
data/seed/v3/SOURCES.md                # provenance for every file above
scripts/places.py                      # shared Google Places client (from scripts/fetch_places.py)
scripts/fetch_branches.py              # Task 1
scripts/fetch_neighbourhoods.py        # Task 2
scripts/fetch_isochrones.py           # Task 3
scripts/fetch_salons.py                # Task 4
tests/scripts/test_places.py           # Task 1 helpers: name filter, matching
tests/scripts/test_isochrones.py       # Task 3: reaches
tests/scripts/test_salons.py           # Task 4: tiling, dedupe, cache
notebooks/branches.ipynb               # vets Task 1 (exists; extend)
notebooks/neighbourhoods.ipynb         # vets Task 2
notebooks/reach.ipynb                  # vets Task 3
notebooks/salons.ipynb                 # vets Task 4
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

### Task 2: Neighbourhoods with market size (female population)

**What we need (market model):** every populated neighbourhood in the emirates we cover, each
with an approximate **female population** (its market size). Relative accuracy is enough; the
sex split must be real, not a flat 49%. Official community-level census figures are **not**
required.

**Files:** Create `scripts/fetch_neighbourhoods.py`. Output: `data/seed/v3/neighbourhoods.geojson`.

**Interfaces:**
- Produces a GeoJSON FeatureCollection. Each feature has properties `id, name, emirate, population_female, population_total, centroid_lat, centroid_lng` and a Polygon geometry. `population_female` is `market(n)`.

- [ ] **Step 1: Confirm sources (research, about 30 min).** Record findings in `SOURCES.md`:

  | Need | Source | Check |
  |---|---|---|
  | **Female population** | **WorldPop** age/sex-structured rasters for ARE (100 m), female bands summed across ages | latest year; licence (CC BY 4.0 expected); download size; which raster reader (`rasterio`, or a lighter one) |
  | Neighbourhood **boundaries + names** | OSM via Overpass: `boundary=administrative` (Dubai communities exist at some admin level) or `place=suburb\|neighbourhood\|quarter` | coverage per emirate; Abu Dhabi, Sharjah, RAK, Fujairah may only have `place` nodes, not polygons. If so, make Voronoi polygons from the nodes, clipped to the emirate |
  | Sanity totals | Dubai Statistics Center, SCAD, emirate-level totals | only to check WorldPop's emirate totals, not as input |

  Scope: every emirate with a lounge (Abu Dhabi, Dubai, Sharjah, Ras Al Khaimah, Fujairah). WorldPop covers all of them with one method, which is what makes all-emirates scope feasible. Bring findings to the user before writing code.
- [ ] **Step 2:** Write `fetch_neighbourhoods.py`: fetch the boundaries, sum the WorldPop female (and total) rasters inside each polygon, drop polygons with no population, write the GeoJSON. Raw rasters go in `data/raw/` (gitignored); record their URLs and checksums in `SOURCES.md`.
- [ ] **Step 3: Vet** in `notebooks/neighbourhoods.ipynb`: emirate totals vs. official totals (within about 15%); female share per neighbourhood (industrial and worker-housing areas well under 49%, residential near 45-50%); the largest neighbourhoods by women (does Jebel Ali Industrial drop out of the top?); compare with the old 50-community seed for Dubai; a choropleth map.
- [ ] **Step 4:** Add a `SOURCES.md` row and commit.

### Task 3: Reach (drive-time isochrones per neighbourhood)

**Why per neighbourhood, not per lounge:** the market is shared out per neighbourhood, among
every salon that can reach it. A lounge-centred catchment would miss competitors just
outside it that still serve its edge neighbourhoods. So each neighbourhood gets its own
isochrone; a lounge's catchment is then simply the neighbourhoods whose isochrone contains it.

**Files:** Create `scripts/fetch_isochrones.py`. Outputs: `data/seed/v3/isochrones.geojson` and `data/seed/v3/lounge_reach.csv`.

**Interfaces:**
- Consumes: `neighbourhoods.geojson` (`id`, `centroid_lat`, `centroid_lng`), `branches.csv` (`branch_id`, `lat`, `lng`: Google's pin), and `travel_time_minutes` from `data/scenarios/baseline.yaml`.
- Produces:
  - `isochrones.geojson`: one feature per neighbourhood × level, properties `neighbourhood_id, level, minutes`.
  - `lounge_reach.csv` columns `neighbourhood_id, level, branch_id`: one row per lounge inside that neighbourhood's isochrone.
  - `scripts/fetch_isochrones.py`: `reaches(isochrone: Polygon, points: dict[str, tuple[float, float]]) -> list[str]` (ids of the points inside).

- [ ] **Step 1: API and key.** **openrouteservice** isochrones (free key; about 500 requests a day, 5 locations and several ranges per request). Neighbourhoods ÷ 5 requests in total, all three levels in each, so about 100-200 requests for a few hundred neighbourhoods: one day's quota. The user creates the key and adds `ORS_API_KEY` to `.env` and `src/config.py`. Typical traffic only (ORS has no live traffic): say so in `SOURCES.md`. Cache each response in `data/raw/isochrone_cache/`.
- [ ] **Step 2: Write the failing test**

```python
# tests/scripts/test_isochrones.py
from shapely.geometry import Polygon

from scripts.fetch_isochrones import reaches


def test_reaches_returns_points_inside_only():
    square = Polygon([(55.0, 25.0), (55.1, 25.0), (55.1, 25.1), (55.0, 25.1)])
    pts = {"in": (25.05, 55.05), "out": (25.2, 55.2)}   # (lat, lng)
    assert reaches(square, pts) == ["in"]
```
- [ ] **Step 3:** Run it. Expected: FAIL. Implement `reaches` with `shapely` (note: shapely points are `(lng, lat)`). Add `shapely` to the `notebook` extra. Run again. Expected: PASS.
- [ ] **Step 4:** Ask the user, then run. **Vet** in `notebooks/reach.ipynb`: isochrones over the map for a few neighbourhoods; per lounge, catchment women at each level; lounges sharing neighbourhoods (cannibalisation); populated neighbourhoods that reach **no** lounge (GROW candidates); the **market area** for Task 4 = the union of the high-level (20 min) isochrones of every neighbourhood that reaches a lounge, with its size in km².
- [ ] **Step 5:** Add a `SOURCES.md` row and commit.

### Task 4: Every salon in the market area, with ratings and review counts

**What we need (market model):** every salon that can reach a neighbourhood in any lounge's
catchment, with its lifetime review count (the share weight). That means the whole **market
area** from Task 3, not just lounge catchments, and **Bedashing's own lounges stay in**:
they're salons in the same share formula.

**Files:** Create `scripts/fetch_salons.py`. Outputs: `data/seed/v3/salons.csv` and `data/seed/v3/salon_reach.csv`.

**Interfaces:**
- Consumes: the market area and `isochrones.geojson` (Task 3), plus `search` and `is_bedashing` from `scripts/places.py`, and `reaches` from `scripts/fetch_isochrones.py`.
- Produces:
  - `salons.csv` columns: `place_id, name, address, lat, lng, rating, review_count, status, primary_type, price_level` (Google's, may be empty), `price_low_aed, price_high_aed` (Google's `priceRange`), `neighbourhood_id` (the polygon it sits in), `price_level_used, price_level_source` (`google` / `neighbourhood` / `emirate` / `unknown`), `is_bedashing, branch_id` (`branch_id` set for Bedashing rows, joined on `place_id` to `branches.csv`), `excluded_reason` (empty, or e.g. `men-only`, `not-operational`, `out-of-set-type`), `fetched_at`. One row per salon.
  - `salon_reach.csv` columns: `neighbourhood_id, level, place_id`.
  - Helpers: `split(bbox) -> list[bbox]`, `dedupe(rows) -> list[dict]`, `fetch_tile(bbox, cache_dir) -> list[dict]`, `tag_bedashing(rows: list[dict], branches: list[dict]) -> list[dict]` (sets `is_bedashing` and `branch_id` by `place_id`), and `impute_price_levels(rows: list[dict]) -> list[dict]` (fills `price_level_used` and `price_level_source`; rows carry `price_level`, `neighbourhood_id`, `emirate`).

**Method:** tile the market area's bounding box into rectangles. Each gets a Text Search
`"beauty salon"` with `locationRestriction` set to that rectangle, paged up to 3 × 20. A tile
that returns a full 60 is split into 4 and re-queried, down to about 250 m. Keep results
inside the market area, dedupe by `place_id`, cache each tile in `data/raw/places_cache/`.
Also query `"nail salon"` and `"hair salon"` on the same tiles **only if** the probe shows
`"beauty salon"` misses them (that triples the cost; the user's call).

**Price fields:** add `places.priceLevel,places.priceRange` to `FIELDS` in `scripts/places.py`.
They bill at the same Enterprise tier as `review_count`, so they cost nothing extra. Store the level **normalised to lowercase without the prefix** (`PRICE_LEVEL_VERY_EXPENSIVE` → `very_expensive`), matching `baseline.yaml`. (A probe
on 2026-10-08 near Bedashing Al Barsha: 9 of 19 competitors had both; the Bedashing lounge had neither.)

**Price imputation** (after the fetch, once each salon has its `neighbourhood_id`): for a salon
without a Google `priceLevel`, use the **median level of priced salons in the same
neighbourhood** (levels are ordinal: inexpensive < moderate < expensive < very expensive); if
the neighbourhood has none, the median for the emirate; if still none, `unknown`. Keep Google's
raw value in `price_level` and the result in `price_level_used`, with its `price_level_source`.
Bedashing rows are not imputed; their level comes from the assumption.

**Competitive set:** exclude (and keep with an `excluded_reason`, not delete) men-only salons
(the name regex from `scripts/fetch_competitors.py`), barbershops, and anything not
`OPERATIONAL`. Decide with the user, from the probe's `primary_type` counts, whether spas and
massage centres count. Home-service salons can't be seen: a stated limitation.

- [ ] **Step 1: Write the failing tests**

```python
# tests/scripts/test_salons.py
from scripts.fetch_salons import dedupe, impute_price_levels, split, tag_bedashing


def test_split_quarters_a_full_tile():
    quads = split((25.0, 55.0, 25.2, 55.2))   # (south, west, north, east)
    assert len(quads) == 4
    assert (25.0, 55.0, 25.1, 55.1) in quads and (25.1, 55.1, 25.2, 55.2) in quads


def test_dedupe_keeps_one_row_per_place():
    rows = [{"place_id": "a", "n": "x"}, {"place_id": "a", "n": "y"}, {"place_id": "b", "n": "x"}]
    assert [r["place_id"] for r in dedupe(rows)] == ["a", "b"]


def test_cached_tile_is_not_rebilled(tmp_path, monkeypatch):
    import scripts.fetch_salons as f
    calls = []
    monkeypatch.setattr(f, "search", lambda body, **kw: calls.append(body) or {"places": []})
    tile = (25.0, 55.0, 25.01, 55.01)
    f.fetch_tile(tile, tmp_path)
    f.fetch_tile(tile, tmp_path)
    assert len(calls) == 1


def test_bedashing_kept_and_joined_not_competitor():
    rows = [{"place_id": "g1", "name": "Bedashing Beauty Lounge Delma"},
            {"place_id": "g2", "name": "Pink Madi Beauty Salon"}]
    out = {r["place_id"]: r for r in tag_bedashing(rows, [{"place_id": "g1", "branch_id": "delma"}])}
    assert out["g1"]["is_bedashing"] and out["g1"]["branch_id"] == "delma"
    assert not out["g2"]["is_bedashing"] and not out["g2"]["branch_id"]


def test_impute_uses_neighbourhood_median_then_emirate():
    rows = [
        {"place_id": "a", "price_level": "expensive", "neighbourhood_id": "n1", "emirate": "Dubai"},
        {"place_id": "b", "price_level": "expensive", "neighbourhood_id": "n1", "emirate": "Dubai"},
        {"place_id": "c", "price_level": "", "neighbourhood_id": "n1", "emirate": "Dubai"},
        {"place_id": "d", "price_level": "moderate", "neighbourhood_id": "n2", "emirate": "Dubai"},
        {"place_id": "e", "price_level": "", "neighbourhood_id": "n3", "emirate": "Dubai"},
    ]
    out = {r["place_id"]: r for r in impute_price_levels(rows)}
    assert (out["c"]["price_level_used"], out["c"]["price_level_source"]) == ("expensive", "neighbourhood")
    assert out["e"]["price_level_source"] == "emirate"            # n3 has no priced salons
    assert (out["a"]["price_level_used"], out["a"]["price_level_source"]) == ("expensive", "google")


def test_impute_unknown_when_nothing_priced():
    rows = [{"place_id": "x", "price_level": "", "neighbourhood_id": "n9", "emirate": "Fujairah"}]
    assert impute_price_levels(rows)[0]["price_level_source"] == "unknown"
```
- [ ] **Step 2:** Run them. Expected: FAIL. Implement `split`, `dedupe`, `fetch_tile`, `tag_bedashing`, `impute_price_levels` and the tiling loop. For an even count of levels, take the lower median (the conservative choice: it doesn't inflate a neighbourhood's price). Run again. Expected: PASS.
- [ ] **Step 3: Probe (ask the user first, about 10-20 calls).** One dense tile (Al Barsha) and one sparse one (Al Dhafra). Report calls per km², salons found, tiles hitting the cap, the `primary_type` mix, and **price-level coverage** (share of salons with a Google `priceLevel`, by level). Extrapolate over the market area's km² to a cost estimate. **Budget warning:** `review_count` is an Enterprise-tier field, so every call bills at Enterprise (1,000 free a month, then $35 per 1,000), and the market area covers most of the urban UAE. Expect roughly 1,000-3,000 calls, so possibly $0-70. **Stop and get approval.** Ways to cut it: drop the high (20 min) level from the market area, or split the run across two calendar months.
- [ ] **Step 4:** Full run with `MAX_CALLS` set to the approved estimate plus 20%. Then compute `salon_reach.csv` with `reaches` for every isochrone.
- [ ] **Step 5: Vet** in `notebooks/salons.ipynb`: price-level coverage by emirate and the share imputed per source; how many competitors survive the price filter per lounge, at `[expensive]` and at the wider `[moderate, expensive, very_expensive]` (if the strict filter leaves most lounges with almost no competitors, raise it with the user before integration); Bedashing's lounges' own Google price levels, if any (a check on the `expensive` assumption); salons per lounge catchment and per 10k women; the review-count distribution (competitors vs. Bedashing: how big is Bedashing's review advantage, i.e. the chain-solicitation caveat?); the `excluded_reason` counts; neighbourhoods reached by zero salons or only zero-review salons; Google vs. the old OSM count for Dubai.
- [ ] **Step 6:** Add `SOURCES.md` rows (competitive-set rules, price fields and imputation, 30-day terms caveat, home-service limitation) and commit.

### Task 5: Hand-off

- [ ] **Step 1:** Run `just test`. Expected: all existing tests and the new `tests/scripts` pass. The pipeline is untouched.
- [ ] **Step 2:** Add a **"Market model"** section to `data/seed/v3/SOURCES.md` (so the app can show it): the formula, the per-neighbourhood rule, the excluded airport lounge, and every limitation listed under *Market model* at the top of this plan.
- [ ] **Step 3:** Add a "Data refresh (v3)" entry to `docs/remaining.md`: what's now in `data/seed/v3/`, the open findings from each notebook, and the follow-up **integration plan**. That plan must include:
  - `apportion(market: dict[n, float], reach: dict[n, list[s]], reviews: dict[s, int]) -> dict[s, float]` with these tests (from Review Focus 6-7):

```python
def test_shares_split_one_neighbourhood_by_reviews():
    out = apportion({"n": 1000}, {"n": ["a", "b"]}, {"a": 300, "b": 100})
    assert out == {"a": 750.0, "b": 250.0}

def test_overlap_never_exceeds_market():
    market = {"n1": 1000, "n2": 500}
    reach = {"n1": ["a", "b"], "n2": ["a", "b"]}
    out = apportion(market, reach, {"a": 1, "b": 1})
    assert sum(out.values()) <= sum(market.values())

def test_zero_review_neighbourhood_stays_unallocated():
    out = apportion({"n": 1000}, {"n": ["a"]}, {"a": 0})
    assert out.get("a", 0.0) == 0.0
```
  - The rubric changes: models gain `emirate` and `place_id`; catchments from `lounge_reach.csv` replace nearest-centroid assignment; the demand signal becomes captured market and share; competition comes from `salon_reach.csv` (Google, not OSM), filtered to `comparable_price_levels` using `price_level_used`; the quality signal is replaced or made relative to nearby salons (ratings only span 4.4-4.9); GROW/WATCH/SKIP uses headroom in neighbourhoods that reach no lounge; the app map handles every emirate; the airport lounge is excluded from market measures and labelled.
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
