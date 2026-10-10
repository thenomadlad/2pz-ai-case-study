# Data inventory: what we have, and what's missing

Everything the app reads is committed in `data/seed/v3/`. Full method and caveats per source:
[`data/seed/v3/SOURCES.md`](../data/seed/v3/SOURCES.md). Tunable assumptions:
`data/scenarios/baseline.yaml`. Row counts are computed from the committed files.

## What we have

| Data | Source | Snapshot | Licence / terms | File(s) | Rows |
|---|---|---|---|---|---|
| Bedashing lounges | Bedashing's store locator, matched to Google Places (pin, rating, lifetime reviews, status) | 2026-10-08 | Locator: public website, no licence stated. Google: see Places below | `data/seed/lounges.json`, `branches.csv` | 24 (Abu Dhabi 15, Dubai 5, Sharjah 2, RAK 1, Fujairah 1) |
| Adults per ~2 km cell | WorldPop 2025 R2025A, 100 m age/sex rasters, aggregated to 0.02° cells with ≥ 500 adults | 2025 estimates, built 2026-10-08 | CC BY 4.0 | `cells.csv`, `emirates.csv` | 2,373 cells (94.4% of UAE adults); 7 emirates |
| Worker housing | OpenStreetMap `landuse=industrial` (Overpass); cell names from OSM admin boundaries and places | 2026-10-09 (admin boundaries 2026-07-28) | ODbL (attribute OSM contributors) | in `cells.csv`; raw polygons in `data/raw/osm/` (not committed) | 3,580 polygons |
| Female-share calibration | Dubai Statistics Center 2022 community sex split, via citypopulation.de | 2022 | Public statistics; republisher's terms not checked | `dubai_community_gender.csv` | 23 communities |
| Drive-time catchments | Mapbox Isochrone API, `driving-traffic`, weekday 12:00 | 2026-10-08 | Mapbox Product Terms (2026-07) §1.9: by default no bulk queries and no caching or storing of results unless expressly permitted. Committed here for the case study; a production build needs Mapbox's permission or a licensed alternative | `lounge_isochrones.geojson`, `cell_isochrones.geojson`, `catchment_cells.csv` | 120 lounge polygons (24 x 5 times); 2,430 cell polygons (810 x 3); 3,613 lounge-cell-level rows |
| Salons (competitors) | Google Places (New) Nearby Search, popularity-ranked 1.8 km circles | 2026-10-09 | Google Maps Platform terms: only `place_id` may be stored indefinitely; refresh the rest within 30 days. This snapshot will go stale against that | `salons.csv`, `growth_salons.csv` | 5,924 salons (3,833 kept; excluded: 2,000 men-only, 54 not operational, 37 not a salon); 1,905 of them from the growth-cell run |
| Search record | Every Places circle, both runs | 2026-10-09 | As above | `search_circles.csv` | 858 circles (576 catchment, 282 growth) |
| Lounge-salon links | Derived: non-excluded salons inside each lounge's polygon; search saturation per lounge | 2026-10-09 | Derived from Places and Mapbox | `lounge_candidates.csv`, `lounge_candidates_by_level.csv`, `lounge_search_saturation*.csv` | 5,903 pairs (15 min); 19,188 (all levels); 24 / 72 |
| Dubai rents | Dubai Land Department open data, Ejari rental contracts registered 2026-07-10 to 2026-10-09, downloaded by hand (captcha, 3-month cap) | 2026-10-10 | Free open data; no licence beyond the site's terms | `dubai_rents_by_area.csv`, `cell_affluence.csv` | 173 DLD areas; 241 Dubai cells with an observed rent (2,132 none) |
| Built form (tested, not used) | EU JRC GHSL R2023A, epoch 2018 (settlement zone, building height) | 2018 data, fetched 2026-10-09 | CC BY 4.0 (acknowledge the European Commission, JRC) | `cell_built_form.csv` | 2,373 cells |
| Search-recall calibration | A full sweep of one ~8 km tile around Al Barsha | 2026-10-09 | Google, as above | `data/raw/places_cache/` (not committed) | one tile |

Not committed, re-fetchable: `data/raw/` (API caches, the DLD download, GHSL tiles, OSM).

**Mapbox isochrones are a cache.** All the drive-time polygons are fetched once by
`scripts/fetch_isochrones.py` and kept, so the model never calls Mapbox at run time (see the licence
note above). `cell_isochrones.geojson` (per-cell 10/15/20-min polygons) is **not read by anything in
`src/`** (only `notebooks/catchments.ipynb` loads it, for inspection): the model and app use `lounge_isochrones.geojson` and `catchment_cells.csv`. It is kept
for the per-cell travel-time work (a Huff / served-demand model, `docs/limitations.md`), which
would otherwise need ~810 Mapbox calls (one per cell) to rebuild.

## Gaps

| Gap | Effect on the analysis | How to fill it | Cost |
|---|---|---|---|
| **Revenue, rent, capex, lease terms** | Nothing measures return on capital; SHRINK means "investigate", not "close" | Bedashing's P&L, leases, fixed-asset register | Needs the client |
| **Capacity: chairs, hours, bookings** | Services delivered can't be measured; a full lounge and an empty one look the same | Bedashing's booking system | Needs the client |
| **Affluence outside Dubai** | Abu Dhabi and the northern emirates are weighted neutral, so they aren't compared like for like with Dubai | ADREC (Abu Dhabi) rental data needs an API subscription (public map refuses queries); Sharjah publishes none | Subscription, unknown price |
| **Competitors in small growth cells** | Cells under 2,000 women outside the catchments have no competitor data | Same circles over the remaining cells: ~2,000 calls | ~$70 |
| **Small salons in dense areas** | Google's 20-result cap hides the long tail; corrected with an *estimated* recall of 0.66 from one tile | Split the full circles (~1,600-6,000 calls) | Free from 1 Nov for the first level; ~$54-210 now |
| **Worker housing not mapped as industrial** | Labour camps in DIP and (very likely) Sonapur are missed, so **Mirdif-35's market is overstated** | DSC community sex splits for all Dubai communities (~220 pages), or manual tagging | Free |
| **Female share outside Dubai** | Calibrated on Dubai only; applied UAE-wide | Abu Dhabi (SCAD) and other emirates rarely publish below region level | Probably unavailable |
| **Bedashing's price level** | Assumed `expensive`; drives which competitors count as premium | Its own menu (Phorest booking pages) | Free; one browser session |
| **Competitor prices** | Only ~36% of candidates have a Google price; popularity and rating stand in for the rest | Fresha menus (partial coverage, scraping) | Free but slow; matching needed |
| **Review age** | Lifetime counts favour older salons | First-review dates need a full review scrape | ~$10-65 for Bedashing; not affordable for competitors |
| **Rush-hour travel times** | Catchments assume typical midday traffic; after-work catchments are smaller | Re-fetch isochrones with an 18:00 departure | ~860 Mapbox calls; free tier |
| **Home-service salons** | Invisible to Google Places as shops; competition understated | No good source | n/a |
| **Income and nationality** | Rent stands in for affluence in Dubai only; nationality mix is ignored | No public cell-level source found | n/a |
| **Data licences for production** | Mapbox and Google terms don't allow keeping this snapshot indefinitely | Re-fetch on a schedule, or license the data | Depends on the vendor |
