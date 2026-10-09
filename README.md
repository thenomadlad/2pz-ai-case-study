# Bedashing network right-sizing

A decision-support app for Bedashing Beauty Lounge's UAE network. It scores each of the 24 lounges
**PROTECT / HOLD / SHRINK** and each populated area beyond a 15-minute drive of every lounge
**GROW / WATCH / SKIP**, from drive-time catchments, a women-15+ market estimate and Google Places
competitors. Every call comes with an AI-written explanation, and every number in that explanation
is checked against the data.

**Live app:** https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/

## Read this first: limitations

This is a first pass we will iterate on. The calls are **a shortlist to test with the business, not
decisions**, and the limitations matter more than the calls. The biggest ones:

- **No money in the model.** No revenue, rent, capex or lease data: it scores location and market
  position only. **SHRINK means "investigate", not "close".**
- **Capture rests on lifetime Google review counts.** Older salons look bigger, new lounges look
  weak, and big crowded markets show tiny shares.
- **The calls move with the assumptions.** 10 of the 23 scored lounges are low confidence; travel
  time (10/15/20 min) matters most.
- **Catchments are midday drive times with no distance decay**, and the competitor search misses
  smaller salons where Google's 20-result cap bites.
- **The anchors and thresholds are judgement**, set from the same data they score.

The full ranked list, with which calls each limitation touches and what would fix it:
[`docs/limitations.md`](docs/limitations.md), also the app's **How it works & limitations** page.

## What it currently says

At the baseline (medium levels: 15-min drive, 60% competitor coverage, 5.5% women in worker
housing):

- **Lounges:** 3 PROTECT (al-ain, al-taif-mall, ras-al-khaimah), 13 HOLD, 7 SHRINK, 1 NOT SCORED
  (the airport lounge serves travellers). **10 of 23** calls are low confidence.
- **The 7 SHRINKs are all Abu Dhabi city lounges** (al-maqta, delma, khaleej-al-arabi,
  mohammed-bin-zayed-city, noya-plaza, shahama, westyas): 87-100% of their women are also reached by
  a sibling, and capture is middling to low. Three of them (shahama, mohammed-bin-zayed-city,
  al-maqta) flip to HOLD in 12-21 of the 27 assumption combinations. Investigate, don't cut.
- **Growth areas:** 4 GROW, all in Sharjah emirate (Sharjah, Al Dhaid, Khor Fakkan, Kalba; 218k
  women between them), and 37 WATCH. Bedashing has no Sharjah lounge, possibly for reasons the model
  can't see (licensing, brand fit, landlords).

Treat these as the places to look first, not as answers.

## Run it

```bash
uv sync --extra dev
uv run streamlit run streamlit_app.py     # http://localhost:8501  (or: just app)
```

No API key needed: the app computes everything in memory from the committed `data/seed/v3/` and
serves the committed AI explanations. `just test` runs the 120 tests. `just notebook` opens the
notebooks (start with `decisions.ipynb`).

## Using the app

Four pages; the loop is **Overview → click a lounge or area → its page → back**.

1. **Overview.** The UAE executive summary (an answer, then ranked arguments with their data), a
   limitations box, and the **what-if panel**: switch travel time, competitor coverage and the
   worker-housing share between low / medium / high, change search recall, or close lounges, and
   every call recomputes against the baseline. Below it, the map: lounges with their calls (hollow =
   low confidence) and growth areas. Click a lounge to see its drive-time polygon, catchment cells
   and premium substitutes; click a lounge or an area for its short pyramid and caveats.
2. **Lounges** (`/lounge?lounge=al-barsha`): the call, pyramid and caveats, how many of the 27
   assumption combinations change it, a catchment map, each signal on its fixed scale, the premium
   substitutes, which siblings share its women, and the factor table (value, unit, threshold,
   meaning).
3. **Areas** (`/area?area=kalba-sharjah`): the call against its two tests, a map of its cells, the
   nearest lounge, and the factor table.
4. **How it works & limitations:** `docs/limitations.md`, how the market model fits together, every
   assumption in `baseline.yaml` with its source, and every scorecard and growth constant with why it
   was chosen.

Links carry the selection, so any page can be shared directly.

## Who it's for

| Role | Who | Uses it to |
|---|---|---|
| **Primary user** | Bedashing's portfolio team (network, real estate, expansion) | form recommendations, stress-test them with what-ifs, lift the explanations into memos |
| **Decision-maker** | COO, accountable for lounge operations and return on capital | approve or question the recommendation from the headline and the reasons |
| **Board** | PE owner's board / operating partner | judge whether the call is defensible: evidence, thresholds, caveats |

## How it decides

**Market.** Women aged 15+ per ~2 km grid cell (WorldPop 2025 adults, rebalanced so worker housing
counts few women). A lounge's **catchment** is the cells within a 15-min drive (Mapbox, typical
midday traffic). Its **premium substitutes** are the most-reviewed premium salons in the catchment
that together hold 60% of its premium reviews. **Capture** = the lounge's Google reviews ÷ (its own
+ its substitutes' reviews, scaled up for salons the search missed).

**Lounges** (`src/model/scorecard.py`). Four signals, each 0-1 on a *fixed* scale, so a lounge's score
doesn't move when a sibling opens or closes:

| Signal | Measure | 0 at | 1 at | Weight |
|---|---|---|---|---|
| Demand | women 15+ in the catchment | 0 | 200k | 1 |
| Cannibalisation | share of them another lounge also reaches | 100% | 0% | 1 |
| Capture | share of premium-substitute reviews | 0% | 15% | 1 |
| Rating | rating minus the substitutes' median | −0.3★ | +0.3★ | ½ |

PROTECT ≥ 0.65, SHRINK ≤ 0.35, HOLD between: strong calls need the signals to agree. Rating counts
half because Google ratings come in 0.1★ steps. **Low confidence** = within 0.05 of a line, a thin
premium market (under 10 premium salons, capture scored neutral), no rating gap, or a call that
changes in 9+ of the 27 combinations of the three assumption levels.

**Growth areas** (`src/model/growth.py`). Populated cells beyond a 15-min drive of every lounge,
grouped by place name. **Big enough?** ≥ 20k women, under 50% of adults in worker housing.
**Unsaturated?** Under 50 premium reviews per 1k women in the cells we searched. Both → GROW, one →
WATCH, neither → SKIP; under 5k women is SKIP, and under half the women searched caps at WATCH.

Every anchor, with why it was chosen, is on the app's How page and in `notebooks/decisions.ipynb`.

## The AI layer

The rules make every call; Claude **explains** them as a pyramid: a one-sentence answer, 2-5
supporting arguments, each backed by 2-5 data points from the fact sheet.

- **The code decides what matters** (`src/explain.py:prioritize`): which arguments appear, and in
  what order, is computed (for a lounge, signals far from neutral in the direction of the call).
- **Grounding check** (`src/explain.py:verify`): the arguments must be exactly the ranked ones; every
  cited value must match the fact sheet; every number in the prose must be a fact or a published
  threshold, correctly rounded. A failure falls back to a deterministic template, and the app labels
  which one you're reading.
- **No key needed to see it.** Explanations are cached in `data/explanations/cache.json`, keyed by a
  hash of the exact numbers, so a stale one is never served; a what-if with changed numbers gets the
  template. All 65 baseline explanations (23 lounges, 41 GROW/WATCH areas, the UAE summary) pass the
  check. They were written in a Claude Code session from the same prompts the API would get, not by
  the API. NOT SCORED and SKIP use the template.
- **Regenerate** after changing the model or data: `just explain` (API, needs `ANTHROPIC_API_KEY`),
  or offline with `python -m src.explain prompts DIR` → write the answers → `check DIR` → `ingest DIR`
  (see `justfile`).

## Data

All committed in `data/seed/v3/`, fetched 2026-10-08/09 by the scripts in `scripts/`. Sources, fetch
dates and caveats: [`data/seed/v3/SOURCES.md`](data/seed/v3/SOURCES.md). What's missing and what
filling each gap would cost: [`docs/data-inventory.md`](docs/data-inventory.md).

| Data | Source | Files |
|---|---|---|
| 24 UAE lounges, Google pin, rating, reviews | Bedashing's store locator + Google Places | `branches.csv` (from `data/seed/lounges.json`) |
| 2,373 ~2 km cells: adults, worker-housing adults | WorldPop 2025, OSM industrial land, Dubai Statistics Center (calibration) | `cells.csv`, `emirates.csv`, `dubai_community_gender.csv` |
| Drive-time catchments, 10/15/20 min | Mapbox isochrones | `lounge_isochrones.geojson`, `catchment_cells.csv`, `cell_isochrones.geojson` |
| 5,924 salons found (3,833 women's salons kept) around lounges and growth cells | Google Places nearby search | `salons.csv`, `lounge_candidates*.csv`, `growth_salons.csv`, `search_circles.csv` |

Tunable values: [`data/scenarios/baseline.yaml`](data/scenarios/baseline.yaml).

## Repo map

```
streamlit_app.py         entry point; pages in src/webapp/pages/ (overview, lounge, area, how)
src/webapp/              map layers, shared rendering, the what-if panel
src/data_v3.py           loads data/seed/v3/
src/market.py            women 15+ per cell, premium substitutes, capture
src/features/lounges.py  catchments, lounge features, growth areas
src/model/scorecard.py   lounge signals, scales, weights, thresholds, confidence (with the reasons)
src/model/growth.py      GROW / WATCH / SKIP tests (with the reasons)
src/baseline.py          one in-memory run per what-if, and its diff against the baseline
src/explain.py           fact sheets, prioritisation, grounding check, cache, prompts
scripts/                 one-off fetches (Google Places, Mapbox, WorldPop/OSM cells)
notebooks/               market_size, catchments, competitors, features, decisions, explanations, branches
docs/limitations.md      ranked limitations: read first
docs/remaining.md        status, decisions, what's left
CONTEXT.md               glossary of domain terms
```

Commands: `just app` · `just test` · `just notebook` · `just explain`.

## Assumptions and evidence

Every assumption the data and market model rest on, with its evidence. Status: **in data** = fetched
and committed · **set** = a chosen value or rule, not measured · **estimate** = a calibrated guess, to
be replaced with better data.

| # | Assumption | Value | Evidence / reasoning | Status |
|---|---|---|---|---|
| 1 | **Which lounges exist** | 24 UAE lounges: Abu Dhabi 15, Dubai 5, Sharjah 2, RAK 1, Fujairah 1 | Bedashing's own store locator (bedashingbeauty.com/lounges). All 24 matched an operational Google Maps listing | in data |
| 2 | **Where each lounge is** | Google Maps pin, not the store locator's | The locator's pins are off by up to 16 km (Shahama 15.9, Al Ain 8.4, Nad Al Sheba 4.8 km); its street addresses agree with Google | in data |
| 3 | **Catchment = drive time** a customer will travel | 10 / **15** / 20 min (low / medium / high), Mapbox typical traffic at a weekday 12:00 departure. Competitors are searched within **2x** (30 min at medium): any salon a catchment resident can reach in 15 min is at most 30 min from the lounge | BrightLocal 2014 (US, 800+ consumers): ~14 min to a hair/beauty salon, women ~5 min more than men. Retail trade-area practice: the primary trade area (50-80% of customers) is a 5-15 min drive. No UAE-specific survey found. TomTom 2025: a Dubai trip takes ~40% longer at evening rush (27 vs 19 min per 10 km), so real catchments are smaller after work | in data |
| 4 | **Market size** of each ~2 km grid cell | Women aged 15+ | Only relative size matters. WorldPop 2025 gives adults per 100 m but a flat 33.6% female share everywhere, so the split is redone (row 13). Grid cells, not official neighbourhoods: OSM neighbourhoods cover only 66% of Dubai's women and none of Fujairah | in data |
| 5 | **How Bedashing's share is estimated** | **Capture** = the lounge's Google reviews ÷ (its reviews + its premium substitutes' reviews x a recall correction), inside its 15-min catchment. Estimated customers = capture x catchment women | Reviews stand in for each salon's draw (revealed preference). Other Bedashing lounges count as substitutes, so overlapping lounges split shared demand. It measures share among premium substitutes, not market penetration. Rejected: splitting every cell among every salon that reaches it (~2,100 Google calls vs 72-144) | in data |
| 6 | **Review counts are lifetime totals** | Google `userRatingCount`, not adjusted for age | Older salons have had longer to collect reviews: a stated limitation. Partly a fair signal too: years of trading build a customer base. Per-year rates were considered and dropped: Google can't sort reviews oldest-first, so the first review needs a full scrape (unaffordable for competitors, and against Google's terms) | in data |
| 7 | **Ratings don't separate lounges** | Not used as an absolute quality score | Google ratings for the 24 lounges span 4.4-4.9 (median 4.6, std 0.12); 17 of 24 sit at 4.5 or 4.6. No link to review count (Spearman ρ = −0.22, p = 0.30) | in data |
| 8 | **Bedashing's price segment** | `expensive` (assumed) | Google has no price level for Bedashing's lounges; to be revisited from its own menu | set |
| 9 | **Premium substitutes** | Women's beauty, hair and nail salons in the catchment that Google prices expensive or very expensive; where Google has no price, those with reviews ≥ the catchment median and rating ≥ 4.3 | A shopper choosing Bedashing compares it with similar places, not budget salons. Google's price level is crowd-sourced spend per person and only 36% of the 2,824 candidates have it, so popularity and rating stand in. Salons priced expensive or above had twice the median reviews (165 vs 77) | in data |
| 10 | **How many substitutes** | The most-reviewed premium salons that together hold **60%** of the catchment's premium reviews (50% / 70% as sensitivity): 60 around Al Barsha, 2-3 in Al Dhafra | Reviews are concentrated in thin markets and spread out in dense ones: a fixed top 20 held 22% of reviews around Al Barsha but 66% around Al Taif Mall, so capture against a fixed k meant different things in each catchment. A coverage share makes lounges comparable. (Fixed k = 20 with 10/30 was the earlier design.) | in data |
| 11 | **Competitive set** | Women's beauty, hair and nail salons (Google primary type), found by 576 small-circle popularity searches over the 15-min catchments, plus 282 over the populated growth cells outside them. Men-only (incl. Arabic-named barbers), closed and non-salon places excluded, kept with a reason | No Google search ranks by review count; on a fully swept tile, small popularity circles found 17 of the true top-20 premium salons, one large text search 0-2. Home-service salons, common in the UAE, are invisible: a stated limitation | in data |
| 12 | **Airport lounge** | Excluded from market measures | It serves travellers, not a neighbourhood | set |
| 13 | **Female share in worker housing** | Adults in OSM industrial land use are 5.5% female (low 1% / high 15%); every other cell is rebalanced so each emirate's female total is unchanged | Dubai Statistics Center 2022: 13 labour-camp communities are 0.1-27% female (5.5% population-weighted), residential ones 43-54%. Against 21 measured communities, error falls from 0.21 (WorldPop's flat 33.6%) to 0.13. Camps not mapped as industrial in OSM are missed (DIP, very likely Sonapur), so Mirdif-35's market is overstated | in data |
| 14 | **Search recall (estimate)** | Where our search hit Google's 20-result cap, it found **66%** of premium reviews; substitutes' reviews are scaled by 1 + (share of full circles) x (1/0.66 − 1), from 1.03 to 1.39 | Calibrated on one fully swept ~8 km tile around Al Barsha (28.6k of 43.7k premium reviews found). An upper bound (that sweep missed salons too), and it assumes other dense areas behave like Al Barsha. Splitting the full circles instead was costed at ~$54-210 and declined. To be replaced if a full sweep is run | estimate |

What these assumptions miss, ranked: [`docs/limitations.md`](docs/limitations.md).
