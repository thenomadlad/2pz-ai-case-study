# Data inventory: what we have, and what's missing

As of 2026-10-09 (branch `data-refresh`). Full sources and caveats: `data/seed/v3/SOURCES.md`.
Tunable assumptions: `data/scenarios/baseline.yaml`. Assumptions with evidence: README, bottom.

## What we have

| Data | Source | Coverage | File(s) | Size |
|---|---|---|---|---|
| Bedashing lounges | Bedashing's own store locator, matched to Google Maps | All 24 UAE lounges (Abu Dhabi 15, Dubai 5, Sharjah 2, RAK 1, Fujairah 1) | `data/seed/lounges.json`, `v3/branches.csv` | 24 rows: Google pin, rating, lifetime reviews, status |
| Population (women 15+) | WorldPop 2025, 100 m grid, aggregated to ~2 km cells | Whole UAE (94% of adults in cells with ≥ 500 adults) | `v3/cells.csv`, `v3/emirates.csv` | 2,373 cells |
| Worker-housing calibration | Dubai Statistics Center 2022 community sex split (via citypopulation.de) | 23 Dubai communities | `v3/dubai_community_gender.csv` | 23 rows |
| Worker-housing locations | OpenStreetMap industrial land use | Whole UAE | `data/raw/osm/` (not committed; re-fetchable) | 3,580 polygons |
| Drive-time catchments | Mapbox Isochrone API, typical traffic, weekday 12:00 | 24 lounges x 10/15/20/30/40 min; 810 catchment cells x 10/15/20 min | `v3/lounge_isochrones.geojson`, `v3/catchment_cells.csv`, `v3/cell_isochrones.geojson` | 120 + 2,430 polygons |
| Competitors | Google Places Nearby (popularity-ranked 1.8 km circles) | Inside the 24 lounges' 15-min catchments | `v3/salons.csv`, `v3/lounge_candidates.csv`, `v3/lounge_search_saturation.csv` | 4,237 salons (2,824 women's-salon candidates) |
| Search-recall calibration | A full sweep of one ~8 km tile around Al Barsha | One tile | `data/raw/places_cache/` (not committed) | 452 salons |

## Gaps

| Gap | Effect on the analysis | How to fill it | Cost |
|---|---|---|---|
| **Revenue, rent, capex, lease terms** | Nothing measures return on capital; SHRINK means "investigate", not "close" | Bedashing's P&L, leases, fixed-asset register | Needs the client |
| **Competitors outside the catchments** | Growth areas are judged on population and distance only; saturation unknown | Same 1.8 km circles over growth areas: 60 calls (cells ≥ 5k women), 282 (≥ 2k), 2,278 (all) | 60 free now; 282 free from 1 Nov (~$7 now); all ~$80 |
| **Small salons in dense areas** | Google's 20-result cap hid the long tail where 31% of circles were full; corrected with an *estimated* recall of 0.66 from one tile | Split the full circles (~1,600-6,000 calls) | Free from 1 Nov for the first level; ~$54-210 now |
| **Worker housing not mapped as industrial** | Labour camps in DIP and (very likely) Sonapur are missed, so **Mirdif-35's market is overstated** | DSC community sex splits for all Dubai communities (~220 pages), or manual tagging | Free; ~4 minutes of polite scraping |
| **Female share outside Dubai** | Calibrated on Dubai only; applied UAE-wide | Abu Dhabi (SCAD) and other emirates rarely publish below region level | Probably unavailable |
| **Bedashing's price level** | Assumed `expensive`; drives which competitors count as premium | Its own menu (Phorest booking pages) | Free; one browser session |
| **Competitor prices** | Only ~36% of candidates have a Google price; popularity and rating stand in for the rest | Fresha menus (partial coverage, scraping) | Free but slow; matching needed |
| **Review age** | Lifetime counts favour older salons | First-review dates need a full review scrape | ~$10-65 for Bedashing; not affordable for competitors |
| **Rush-hour travel times** | Catchments assume typical midday traffic; after-work catchments are smaller | Re-fetch isochrones with an 18:00 departure | ~860 Mapbox calls; free tier |
| **Home-service salons** | Invisible to Google Places as shops; competition understated | No good source | n/a |
| **Income and nationality** | A woman in a villa compound counts the same as one in a shared flat | No public cell-level source found | n/a |
