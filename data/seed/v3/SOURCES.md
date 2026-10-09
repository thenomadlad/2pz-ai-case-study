# Sources for data/seed/v3

## Catchment travel time

Set in `data/scenarios/baseline.yaml` as `travel_time_minutes` (drive time, minutes).

| Level | Minutes | Why |
|---|---|---|
| low | 10 | Retail trade-area practice: the primary trade area (50-80% of customers) sits within a 5-15 min drive; convenience visits (nail top-ups, repairs) are the most proximity-driven |
| medium | 15 | BrightLocal (2014, US, 800+ consumers): people will drive ~14 min to a hair/beauty salon; 15 min is the standard franchise screening zone |
| high | 20 | Same survey: women travel ~5 min longer than men for a hair/beauty salon; loyal clients travel far further (Amex UK puts hairdressers top for long trips). Top of the 5-20 min range used in retail drive-time analysis |

Caveats:
- No UAE-specific survey was found. All evidence is US/UK or generic retail practice.
- Isochrones are computed at typical traffic. TomTom Traffic Index 2025: a 10 km drive takes
  ~19 min on average in Dubai but ~27 min at evening rush, so a "15 minute" catchment
  is much smaller after work, when salon demand peaks. Abu Dhabi: ~22 min per 10 km.

Sources:
- BrightLocal, Local Business Travel Times (2014): https://brightlocal.com/research/local-business-travel-times/
- Atlas, Define trade areas and catchment zones: https://atlas.co/blog/define-trade-areas-and-catchment-zones-for-new-sites/
- Smappen, Franchising 101 (influence area): https://smappen.com/blog/franchising-101-typical-influence-area
- Modern Barber / Amex UK: https://modernbarber.co.uk/barbers-top-the-list-of-small-businesses-brits-travel-furthest-to-visit
- TomTom Traffic Index 2025, Dubai: https://www.tomtom.com/traffic-index/dubai-traffic/
- TomTom Traffic Index 2025, Abu Dhabi: https://www.tomtom.com/traffic-index/abu-dhabi-traffic/

## Branches (`branches.csv`, 24 rows, fetched 2026-10-08)

Script: `scripts/fetch_branches.py`.

- **Which lounges exist:** Bedashing's own store locator, snapshot in `data/seed/lounges.json`
  (`bedashingbeauty.com/wp-admin/admin-ajax.php?action=asl_load_stores&load_all=1`, read in a
  browser because Cloudflare blocks plain HTTP). 24 lounges: Abu Dhabi 15 (incl. Al Ain, Al
  Dhafra), Dubai 5, Sharjah 2, Ras Al Khaimah 1, Fujairah 1.
- **Location, rating, review count, status:** Google Places (New) Text Search, one call per
  lounge, matched by the lounge's title in the Google name or address, else the nearest
  Bedashing listing within 1 km. All 24 matched; all OPERATIONAL.
- **`lat`/`lng` are Google's pin.** The locator's own pins are off by up to 16 km (Shahama
  15.9, Al Ain 8.4, Nad Al Sheba 4.8 km); its street addresses agree with Google, so the
  locator pin is kept only as `locator_lat`/`locator_lng`.
- **`branch_id`** is the slugified title; the locator's slugs are stale (Noya Plaza's slug
  is `zayed-international-airport-abu-dhabi`).
- Ratings span 4.4-4.9 (median 4.6); review counts 215-2,465 (median 755).
- Google terms: only `place_id` may be stored indefinitely; refresh the rest within 30 days.

## Review counts: lifetime totals, not a rate

`review_count` in `branches.csv` (and in `competitors.csv`, Task 4) is Google's **lifetime**
total. It is used as-is, with no adjustment for age.

**Caveat:** older salons have had longer to collect reviews, so the count partly measures age,
not just how busy a salon is. Noya Plaza (215) will read as weak partly because it is new.
**Why it's still acceptable:** age is not pure noise. A salon that has traded for years has
built a customer base and a place in local habits, so its larger review count partly
reflects a genuinely stronger hold on its area. The app should label the measure
"lifetime reviews", not "busyness" or "footfall".

**Considered and dropped:** reviews per year since the first review. Google Maps can't sort
reviews oldest-first, so finding the first review needs a full scrape of every review
(~21k for Bedashing's lounges; unaffordable for competitors) and breaks Google's terms.

## Price segment (assumption)

- **Source:** Google Places `priceLevel` (inexpensive / moderate / expensive / very expensive) and
  `priceRange` (AED from-to): crowd-sourced "spend per person" from Google users, in coarse
  brackets, not a price list.
- **Coverage is thin:** a 1-call sample near Bedashing Al Barsha found 9 of 19 competitors priced,
  but the larger probe (2026-10-08) found ~20% of salons priced around Al Barsha and ~4% around
  Al Dhafra.
- **Bedashing:** its lounges have no Google price. Its level is an **assumption**, `expensive`
  (`bedashing_price_level` in `data/scenarios/baseline.yaml`), to be revisited from its own menu
  (Phorest booking pages).
- **Use:** a competitor counts as a premium substitute if Google prices it expensive or very
  expensive (`comparable_price_levels`); where Google has no price, popularity and rating stand
  in (see "Competitors", Task 4). No imputation: neighbourhood-median imputation was planned
  and dropped once coverage turned out to be ~20%.

## Market size (`cells.csv`, `emirates.csv`, `dubai_community_gender.csv`, built 2026-10-08)

Script: `scripts/build_cells.py`. Notebook: `notebooks/market_size.ipynb` (model structure,
assumptions, validation).

- **Population:** WorldPop 2025, R2025A v1, constrained, 100 m, age/sex structures for the UAE
  (DOI 10.5258/SOTON/WP00841, CC BY 4.0): the 16 female and 16 male rasters for ages 15-90+, from
  `https://data.worldpop.org/GIS/AgeSex_structures/Global_2015_2030/R2025A/2025/ARE/v1/100m/constrained/`.
  UAE adults 15+: 9.42M.
- **WorldPop's sex split is flat:** every pixel is 33.6% female (one national ratio). We keep its
  adults and redo the split.
- **Worker housing** = adults inside OSM `landuse=industrial` (3,580 polygons, Overpass,
  2026-10-09). Their female share is `worker_housing_female_share` (low 1% / medium 5.5% / high
  15%, `baseline.yaml`); every other pixel gets the share that keeps its emirate's WorldPop female
  total.
- **Calibration and validation:** Dubai Statistics Center 2022 community estimates with the sex
  split, republished by citypopulation.de (23 communities, `dubai_community_gender.csv`).
  Labour-camp areas 0.1-27% female (5.5% population-weighted); residential 43-54%. Against 21
  of them, located by OSM place points: mean absolute error 0.21 (WorldPop) → 0.13 (corrected).
- **Limitation:** camps not mapped as industrial in OSM are missed: Dubai Investment Park 1-2,
  Ras Al Khor Industrial 1-2 and very likely Sonapur (Muhaisnah 2), so **Mirdif-35's market is
  overstated**. One false positive: Al Qusais Industrial 4 (residential, 59% industrial land). OSM
  labour-accommodation tags were tried as a second signal and rejected (79 features UAE-wide,
  none near Sonapur).
- **Grid:** 0.02° cells (~2.2 x 2.0 km), cells with ≥ 500 adults: 2,373 cells, 94.4% of UAE adults.
  Names from OSM admin boundaries (level 10, then 8, 2026-07-28 snapshot) or the nearest OSM place
  within 3 km. Cells, not official neighbourhoods, because OSM neighbourhoods cover 66% of
  Dubai's women, Sharjah's are whole towns and Fujairah has none.

## Catchments (`lounge_isochrones.geojson`, `catchment_cells.csv`, `cell_isochrones.geojson`, fetched 2026-10-08)

Script: `scripts/fetch_isochrones.py`. Notebook: `notebooks/catchments.ipynb`.

- **Source:** Mapbox Isochrone API, profile `driving-traffic`, `depart_at` 2026-10-13T12:00 (a
  weekday midday: Mapbox's typical traffic at that time). `isochrone_depart_at` in `baseline.yaml`.
- **Lounges:** 24 x {10, 15, 20, 30, 40} min (catchment levels, plus 2x each as the competitor
  search bound). 48 requests.
- **Catchment cells:** cells whose centre is inside a lounge's polygon: 257 / 542 / 810 at
  10 / 15 / 20 min.
- **Cells:** each of the 810 catchment cells x {10, 15, 20} min, starting from the cell (customers
  drive from home). 810 requests.
- Polygons are simplified to ~200 m in the committed files; memberships are computed on the
  full-detail polygons (cached in `data/raw/isochrone_cache/mapbox/`).
- **Tried first: openrouteservice.** Its free key allows ~250 isochrones a day, counted per
  location (not per request); 810 cells would have taken 3+ days, and it has no traffic model.
- **Limitations:** typical midday traffic, not rush hour (TomTom 2025: Dubai evening trips take
  ~40% longer, so after-work catchments are smaller); cell membership by centre point.

## Competitors (`salons.csv`, `lounge_candidates.csv`, fetched 2026-10-09)

Script: `scripts/fetch_salons.py`. Notebook: `notebooks/competitors.ipynb`.

- **Source:** Google Places (New) **Nearby Search**, `includedPrimaryTypes` = beauty_salon,
  hair_salon, nail_salon, beautician, hair_care; `rankPreference` = POPULARITY; 20 results per
  call. 576 circles of 1.8 km radius on a gap-free hexagonal grid over the union of the 15-min
  catchments: 576 calls, inside the monthly free tier. The first design's per-lounge text
  searches (144 calls) are merged in from cache.
- **Why this method (validation):** on a fully swept ~8 km tile around Al Barsha (probe, 62 calls),
  recall of the true top-20 premium salons by reviews was 0-2/20 for one large text search per
  lounge, 5/20 for one large popularity search, and **17/20 for small popularity circles** (8/10 at
  k = 10, 25/30 at k = 30, re-measured on the final run). No Google search ranks by review count.
- **Rows:** 4,237 salons inside some lounge's 15-min catchment; 2,824 candidates after exclusions:
  men-only 1,337 (barber_shop type; "gents/men/barber" names; Arabic حلاق "barber", رجال "men"),
  not operational 44, not a women's salon 32. Other Bedashing lounges inside a catchment are
  candidates (added from `branches.csv`).
- **Selection is not baked in:** each lounge's premium substitutes are picked from
  `lounge_candidates.csv` with `competitor_coverage` (the most-reviewed premium salons holding
  50/60/70% of the catchment's premium reviews), `premium_min_rating` (4.3) and
  `comparable_price_levels` (expensive, very expensive) from `baseline.yaml`.
- **Search saturation and recall (estimate):** `lounge_search_saturation.csv` gives, per lounge,
  the share of search circles over its catchment that returned Google's cap of 20 (5% al-dhafra
  to 76% zawaya-walk). On the fully swept Al Barsha tile (94% of circles full) our search found
  66% of the premium reviews (28.6k of 43.7k): `search_recall: 0.66`. Substitutes' reviews are
  scaled by 1 + full share x (1/0.66 − 1). An upper bound on recall (the sweep missed salons too);
  replace it if a full sweep is ever run. Splitting full circles instead was costed at ~$54-210
  and declined.
- **Limitations:** lifetime review counts favour older salons; chains likely push for more
  reviews; home-service salons are invisible; ~36% of candidates have a Google price, so the
  premium test mostly uses the reviews-and-rating stand-in; capture is a share of the premium end,
  not the whole market; al-dhafra and
  al-falah have only 6-7 premium salons, so their capture is unreliable.
- Google terms: only `place_id` may be stored indefinitely; refresh the rest within 30 days.
