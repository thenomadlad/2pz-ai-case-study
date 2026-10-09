# Bedashing network right-sizing

A decision-support app for Bedashing Beauty Lounge's Dubai network. It labels each of the 9 branches **PROTECT / HOLD / SHRINK** and each of 50 Dubai communities **GROW / WATCH / SKIP** for a new branch. Every call comes with an AI-written explanation, and every number in that explanation is checked against the data.

**Live app:** https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/

## Run it

```bash
uv sync --extra dev
uv run streamlit run streamlit_app.py     # http://localhost:8501
```

No API key needed. On first load the app builds its data from committed seed files. `just test` runs the 115 tests.

## Using the app

Three pages, one loop: **start on the Overview, click a branch or an area, dig into its page, go back, repeat.**

1. **Overview.** The executive summary comes first: one answer, then the ranked arguments behind it, each with its data. Below it is the map, with a side panel holding the layer toggles and a legend that states the thresholds (PROTECT ≥ 0.65, GROW = over 5 km from a branch *and* under 5 rival salons per 10k women, and so on). Every branch carries a flag. Click a branch and its catchment appears (its communities, tinted, with a line to each); click a branch or an area and its own short pyramid appears underneath. **Deselect** clears it.
2. **Open area page →** shows one community:
   - **What's left:** salon headroom (how many more salons it could support at Dubai's median density, after competitors and Bedashing), women not covered by Bedashing, and Bedashing's fair-share capture, a naive estimate that treats every salon as equally attractive;
   - its pyramid and GROW / WATCH / SKIP tests against their thresholds;
   - a map of its catchment, with every competitor salon and branch (hover for data);
   - which branch's catchment it's in, and whether that's contested;
   - the competitor salons there, by name, and links to its branches.
3. **Open branch page →** shows one branch: its decision and pyramid, a map of its catchment, the areas in that catchment (each linking to its area page), each signal on its fixed scale, and a what-if form.
4. **Back to overview** reopens the same panel, ready for the next one. Every factor table lists each input's value, unit, **threshold** and meaning, and wraps rather than scrolls.

Links carry the selection (`/area?area=naif`, `/branch?branch=al-safa-2`), so any page can be shared directly.

## Who it's for

The app supports one conversation between three roles:

| Role | Who | Uses it to |
|---|---|---|
| **Primary user** | Bedashing's portfolio team (network, real estate, expansion) | form recommendations, stress-test them with scenarios, lift the explanations into memos |
| **Decision-maker** | COO, accountable for branch operations and return on capital | approve or question the recommendation from the headline and the reasons |
| **Board** | PE owner's board / operating partner | judge whether the call is defensible: evidence, thresholds, caveats |

**Dubai only, by design.** Dubai has 9 of Bedashing's 23 UAE branches, and it's the only emirate with community-level population data.

## What it currently says

- **3 PROTECT** (jumeirah-park, al-warqa, city-walk), **5 HOLD**, **1 SHRINK** (al-safa-2: 87% of its catchment is contested by a sibling branch, and it has a small, competitive market).
- **7 GROW** areas, all in Deira / old Dubai, Al Qusais and Muhaisnah. Each is 6.8–10.5 km from the nearest branch, with fewer than 5 rival salons per 10k women. Bedashing's network sits in the south and west, and the north-east is the gap.
- Scenario example: move al-safa-2 into Deira and it flips SHRINK → PROTECT, and five Deira GROW areas become WATCH.

## How it decides

**Branches.** There are four signals, each scored 0–1 on a *fixed* scale, so a branch's score doesn't move when a sibling changes. They're averaged with equal weights.

| Signal | Measure | 0 at | 1 at | Why that scale |
|---|---|---|---|---|
| Demand | female residents nearest this branch | 0 | 150k | roughly what the busiest branches serve |
| Cannibalisation | % of catchment where a sibling is nearly as close | 100% | 0% | already a share |
| Competition | rival salons per 10k female residents | 15 | 0 | Dubai median ≈ 5, 75th percentile ≈ 11 |
| Quality | 2GIS rating | 4.0★ | 5.0★ | salon ratings cluster above 4 |

PROTECT ≥ 0.65, SHRINK ≤ 0.35, HOLD in between. The wide middle is deliberate: with no revenue data, the model should only make strong calls when the signals agree. A healthy network can have zero SHRINKs. Confidence is low near a threshold or when an input is missing.

**Opportunity areas.** Each community gets two questions:
- **Underserved?** The nearest branch is more than 5 km away.
- **Unsaturated?** It has fewer than 5 rival salons per 10k women.

Both → GROW, one → WATCH, neither → SKIP. Areas with fewer than 20k women, or that already host a branch, are SKIP. Industrial / worker-housing areas are capped at WATCH, because the uniform 49% female share badly overstates their demand.

**Geography.** Catchments use straight-line nearest-branch assignment of community centroids. Each competitor counts toward its nearest community, within 3 km. Travel time is out of scope: it's simple and stated, not correct.

## The AI layer

The rules make every decision; Claude (Opus 5.5, low effort) **explains** them:
- a **pyramid** for every decision and for the network as a whole: a one-sentence **answer**, then **2–5 supporting arguments**, each backed by **2–5 data points** copied from the fact sheet;
- a plain-language **caption for the factor table**. Every table also shows each factor's unit and meaning.

**The code decides what matters; the AI writes it up.** Which arguments appear, and in what order, is computed (`src/explain.py:prioritize`). For a branch, a signal is an argument when its score sits at least 0.1 from neutral in the direction of the call: weaknesses for SHRINK, strengths for PROTECT, either for HOLD. Strongest comes first, with at least 2 arguments. For areas, the two 2×2 tests come first, then demand. The executive summary covers where to cut back, where to grow, what to protect, how sure we are and what the model can't see, leaving out any that are empty. So "why is this the top reason?" has a deterministic answer.

**Grounding check** (`src/explain.py:verify`): the arguments must be exactly the ranked ones, in order; every cited field must exist with the same value; and every number in the prose must be a fact or a published threshold, correctly rounded at the precision written ("4,400" for 4,431 passes, "4,500" doesn't). A failed check is retried once with the errors fed back. If it fails again, the deterministic template is used instead. The app always labels which one you're reading.

**No key needed to see it.** Explanations are generated once with `just explain` and committed in `data/explanations/cache.json`, keyed by a hash of the exact numbers, so a stale explanation can never be served. In a scenario, a branch whose numbers changed gets a live explanation if a key is set, and the template otherwise.

All 59 baseline explanations (9 branches, 50 areas) are generated and pass the grounding check. Regenerate after changing the model or data with `just explain` (needs `ANTHROPIC_API_KEY` in `.env`; re-runs only fill gaps).

## Where to trust it, and where not

**Trust it for** a first screen of location and market position, for spotting which branches sit near a threshold, and for seeing how a relocation or new site reshapes catchments.

**Don't trust it for** anything about return on capital. There's no revenue, rent, capex or lease data. Treat SHRINK as "investigate first", not "close". A return-on-capital view would need, per branch:

| Input | Where analysts would get it |
|---|---|
| Revenue | branch P&L / POS system |
| Rent and service charges | lease agreements |
| Fit-out capex and remaining book value | fixed-asset register |
| Lease expiry and break clauses | lease agreements |
| Staff cost and utilisation | payroll and booking system |

Known weak spots:
- **Equal weights let strong signals hide a fatal one.** nad-al-sheba serves only ~3k women but scores HOLD (0.60), because it has no cannibalisation and little competition.
- **Straight-line catchments** ignore malls, roads and habit. City-walk's catchment (394k women) is an artefact of only 9 branches covering all of Dubai.
- **OSM competitor counts are a lower bound.** Gents' salons are filtered by tag and by name, imperfectly.
- **Female population is a uniform 49% estimate.** The per-community split isn't published.
- **Thresholds are judgement calls** taken from the data distribution. There are no outcomes to fit them to.

## Data

| Data | Source | Notes |
|---|---|---|
| 9 branches, ratings, reviews | 2GIS, hand-collected | `data/seed/branches.csv`; sheikh-zayed-road has no rating (scored neutral) |
| 50 communities, population | Dubai Statistics Center 2022/24 bulletin | `data/seed/communities.csv`; female share estimated at 49% |
| 768 competitor salons | OpenStreetMap (Overpass) | `data/seed/competitors.csv`, pulled by `scripts/fetch_competitors.py` |

The research behind these sources, including what was tried and rejected (Dubai Pulse, Fresha pricing), is in `docs/history.md`.

## Repo map

```
streamlit_app.py           3 pages: Overview (summary, map, click-through), Areas, Branches
src/webapp/pages/          overview.py, area.py, branch.py; views.py holds shared rendering
src/acquire/               seed CSVs -> data/raw/*.json
src/features/              nearest-branch catchments, competitor counts, per-community features
src/model/rubric.py        branch signals, scales, thresholds (with the reasons)
src/model/opportunity.py   GROW/WATCH/SKIP rule
src/explain.py             glossary, fact sheets, LLM explanations, grounding check, cache
src/scenario/              in-memory what-if runs diffed against the baseline
docs/remaining.md          gap analysis vs. the brief, decisions, what's left
docs/designs/v2.md         design and decisions for the current model
docs/history.md            v0-v1 development story and decision register
CONTEXT.md                 glossary of domain terms
```

Commands: `just all` (rebuild the baseline) · `just app` · `just explain` · `just scenario data/scenarios/example-perturbations.yaml` · `just test`.

## Assumptions and evidence (data refresh, in progress)

A data refresh is replacing the hand-curated seed: 4 of its 9 "Dubai branches" don't exist.
The live app above still runs on the old data until the refresh is wired in. Below is every
assumption the new data and market model rest on, with its evidence. Full sources, fetch dates
and caveats are in [`data/seed/v3/SOURCES.md`](data/seed/v3/SOURCES.md); the tunable values are in
[`data/scenarios/baseline.yaml`](data/scenarios/baseline.yaml); the work plan is
[`docs/superpowers/plans/2026-10-08-data-refresh.md`](docs/superpowers/plans/2026-10-08-data-refresh.md).

Status: **in data** = fetched and committed · **set** = value chosen, used once the data lands · **planned** = method agreed, data not fetched yet.

| # | Assumption | Value | Evidence / reasoning | Status |
|---|---|---|---|---|
| 1 | **Which lounges exist** | 24 UAE lounges: Abu Dhabi 15, Dubai 5, Sharjah 2, RAK 1, Fujairah 1 | Bedashing's own store locator (bedashingbeauty.com/lounges). All 24 matched an operational Google Maps listing | in data |
| 2 | **Where each lounge is** | Google Maps pin, not the store locator's | The locator's pins are off by up to 16 km (Shahama 15.9, Al Ain 8.4, Nad Al Sheba 4.8 km); its street addresses agree with Google | in data |
| 3 | **Catchment = drive time** a customer will travel | 10 / **15** / 20 min (low / medium / high), Mapbox typical traffic at a weekday 12:00 departure. Competitors are searched within **2x** (30 min at medium): any salon a catchment resident can reach in 15 min is at most 30 min from the lounge | BrightLocal 2014 (US, 800+ consumers): ~14 min to a hair/beauty salon, women ~5 min more than men. Retail trade-area practice: the primary trade area (50-80% of customers) is a 5-15 min drive. No UAE-specific survey found. TomTom 2025: a Dubai trip takes ~40% longer at evening rush (27 vs 19 min per 10 km), so real catchments are smaller after work | in data |
| 4 | **Market size** of each ~2 km grid cell | Women aged 15+ | Only relative size matters. WorldPop 2025 gives adults per 100 m but a flat 33.6% female share everywhere, so the split is redone (row 13). Grid cells, not official neighbourhoods: OSM neighbourhoods cover only 66% of Dubai's women and none of Fujairah | in data |
| 5 | **How Bedashing's share is estimated** | **Capture** = the lounge's Google reviews ÷ (its reviews + its top-k premium substitutes' reviews), inside its 15-min catchment. Estimated customers = capture x catchment women | Reviews stand in for each salon's draw (revealed preference). Other Bedashing lounges count as substitutes, so overlapping lounges split shared demand. It measures share among premium substitutes, not market penetration. Rejected: splitting every cell among every salon that reaches it (~2,100 Google calls vs 72-144) | planned |
| 6 | **Review counts are lifetime totals** | Google `userRatingCount`, not adjusted for age | Older salons have had longer to collect reviews: a stated limitation. Partly a fair signal too: years of trading build a customer base. Per-year rates were considered and dropped: Google can't sort reviews oldest-first, so the first review needs a full scrape (unaffordable for competitors, and against Google's terms) | in data (lounges) |
| 7 | **Ratings don't separate lounges** | Not used as an absolute quality score | Google ratings for the 24 lounges span 4.4-4.9 (median 4.6, std 0.12); 17 of 24 sit at 4.5 or 4.6. No link to review count (Spearman ρ = −0.22, p = 0.30) | in data |
| 8 | **Bedashing's price segment** | `expensive` (assumed) | Google has no price level for Bedashing's lounges; to be revisited from its own menu | set |
| 9 | **Premium substitutes** | Women's beauty, hair and nail salons in the catchment that Google prices expensive or very expensive; where Google has no price, those with reviews ≥ the catchment median and rating ≥ 4.3 | A shopper choosing Bedashing compares it with similar places, not budget salons. Google's price level is crowd-sourced spend per person and only ~20% of salons have it (probe near Al Barsha; ~4% near Al Dhafra), so popularity and rating stand in. Salons priced expensive or above had twice the median reviews (165 vs 77) | set |
| 10 | **Top k substitutes** | k = **20** (10 and 30 as sensitivity) | Reviews are concentrated in thin markets and spread out in dense ones: the top 10 salons hold 82% of reviews around Al Dhafra but 24% around Al Barsha. So a fixed k leaves out more of the market in dense cities and overstates capture there; the notebook shows each lounge at k = 10/20/30 and how much of the market the k cover | set |
| 11 | **Competitive set** | Women's beauty, hair and nail salons. Men-only and closed salons excluded (kept with a reason) | Bedashing is a women's beauty lounge. Home-service salons, common in the UAE, are invisible in the data: a stated limitation | planned |
| 12 | **Airport lounge** | Excluded from market measures | It serves travellers, not a neighbourhood | set |
| 13 | **Female share in worker housing** | Adults in OSM industrial land use are 5.5% female (low 1% / high 15%); every other cell is rebalanced so each emirate's female total is unchanged | Dubai Statistics Center 2022: 13 labour-camp communities are 0.1-27% female (5.5% population-weighted), residential ones 43-54%. Against 21 measured communities, error falls from 0.21 (WorldPop's flat 33.6%) to 0.13. Camps not mapped as industrial in OSM are missed (DIP, very likely Sonapur), so Mirdif-35's market is overstated | in data |

**Known limitations of the market model.** There's no distance decay inside the drive time:
every reachable salon competes equally (a Huff gravity model is the natural upgrade, and the
three travel-time levels are the sensitivity check). Chains likely push for more reviews than
independents, which inflates Bedashing's share. Income and nationality mix are ignored. Mall
lounges draw beyond their drive-time zone. There's still no revenue, rent or capex data, so
nothing here measures return on capital.
