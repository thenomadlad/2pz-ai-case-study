# Bedashing network right-sizing

A decision-support app for Bedashing Beauty Lounge's UAE network. It scores each of the 24 lounges
**PROTECT / HOLD / SHRINK** and each populated area beyond a 15-minute drive of every lounge
**GROW / WATCH / SKIP**, from drive-time catchments, a women-15+ market estimate (weighted by affluence where Dubai rents
are known) and Google Places competitors. Every call comes with an AI-written explanation, and every number in that explanation
is checked against the data.

**Live app:** https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/

## Look at this in 5 minutes

1. **[Overview](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/):** the COO's
   question, the executive summary and three at-stake figures (5 SHRINK lounges, 233,883 women in
   shared cells; 5 GROW areas, 261,797 women).
2. **Tick "All catchments (overlap)"** above the map: the red cells shared by 2+ lounges are the
   SHRINK story; the PROTECT lounges sit alone.
3. **[delma](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/lounge?lounge=delma)
   (SHRINK):** the AI pyramid with *so what / now what*, the factor table's contributions, which
   siblings share its women, and *What would change the call* (shared catchment 98% → 55% makes it
   HOLD). High confidence: it holds in all 81 assumption combinations.
4. **[Kalba](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/area?area=kalba-sharjah)
   (GROW):** 27,638 addressable women against a 20,000 line, 44 premium reviews per 1k against 150;
   high confidence.
5. **The fallback:** in the Overview's **🧪 What if…?** panel set travel time to 20 min and reopen
   mohammed-bin-zayed-city from its map panel: it turns HOLD (0.36) and the text switches to the
   labelled template.
6. **[How it works & limitations](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/how)**,
   then the limitations below.

The full ten-minute version, with the AI layer and where not to trust it:
[`docs/walkthrough.md`](docs/walkthrough.md).

## Read this first: limitations

This is a first pass we will iterate on. The calls are **a shortlist to test with the business, not
decisions**, and the limitations matter more than the calls. The biggest ones:

- **No money in the model.** No revenue, rent, capex or lease data: it scores location and market
  position only. **SHRINK means "investigate", not "close".**
- **Capture rests on lifetime Google review counts.** Older salons look bigger, new lounges look
  weak, and big crowded markets show tiny shares.
- **Affluence is observed in Dubai only.** Demand weights women by their cell's median household
  rent (DLD, 3 months), which exists for 241 Dubai cells; everywhere else is weighted neutral, so
  Dubai and the other emirates are not compared like for like.
- **The calls move with the assumptions.** 10 of the 23 scored lounges are low confidence; travel
  time (10/15/20 min) matters most.
- **Catchments are midday drive times with no distance decay**, and the competitor search misses
  smaller salons where Google's 20-result cap bites.
- **The anchors and thresholds are judgement**, set from the same data they score.

The full ranked list, with which calls each limitation touches and what would fix it:
[`docs/limitations.md`](docs/limitations.md), also the app's **How it works & limitations** page.

## Who it's for, and what it decides

| Role | Who | Uses it to |
|---|---|---|
| **Primary user** | Bedashing's portfolio team (network, real estate, expansion) | form recommendations, stress-test them with what-ifs, lift the explanations into memos |
| **Decision-maker** | COO, accountable for lounge operations and return on capital | approve or question the recommendation from the headline and the reasons |
| **Board** | PE owner's board / operating partner | judge whether the call is defensible: evidence, thresholds, caveats |

Each label maps to a decision the COO already makes (definitions: [`CONTEXT.md`](CONTEXT.md), "Decisions"):

| COO decision | Label | What it asks |
|---|---|---|
| **Lease renewal** (each lounge, at its lease event) | **PROTECT** | Keep and defend: renew, don't relocate, respond to a competitor opening nearby |
| | **HOLD** | No portfolio action this cycle; revisit at the next lease event, or sooner if a signal crosses a line |
| | **SHRINK** | Investigate, don't close: before the lease event, review downsizing or consolidating into the sibling that shares most of its catchment |
| **Site search** (expansion plan) | **GROW** | Start a site search: a shortlist for site visits, verified on the ground before committing |
| **Revisit later** | **WATCH** | Don't act now; revisit when the named failing test changes |
| **No action** | **SKIP** | Too small or already crowded. (The airport lounge is NOT SCORED: it serves travellers.) |

**North star: services delivered**, the demand our lounges actually serve, bounded by their
capacity. The model can't measure it yet. Its nearest proxy is **estimated women captured**
(capture x addressable women), which the lounge factor table shows but the scorecard doesn't use.
**Capacity is not modelled at all** (no chairs, hours or utilisation), so the model can't tell a
full lounge from an empty one, and a SHRINK is driven by raw catchment overlap, not by services
that would be lost. Read the calls with that in mind.

**One flow, question to action.** *"Which Abu Dhabi lounges should we review before their
leases?"* → Overview: the summary and map show 5 SHRINKs, all in Abu Dhabi city → click
**delma** → its page: 98% of its women are also reached by a sibling (the shared-women table
names which: khaleej-al-arabi 73%, ministries-complex 69%), capture is 2%, and the call is high
confidence: it holds in all 81 assumption combinations → action: put delma on the lease-review
list with the sibling named, and ask finance for its P&L before anyone says "close".

**Why a hosted web app.** The COO opens a link: nothing to install, and every lounge and area has
its own URL, so a recommendation can be sent as a link to the evidence. The portfolio team runs
what-ifs in the same place the COO reads the answer, and the board sees the same numbers.

## Out of scope, and why

Our job ends at **allocating lounges to neighbourhoods**: where the network should be denser,
thinner or new. Out of scope:

- **The P&L: revenue, rent, capex, lease terms.** We have none of it, and it is Bedashing's own
  data. It decides whether a SHRINK is closed; the model only says which lounges to look at.
- **In-branch staffing and capacity.** How many chairs and stylists a lounge needs is an
  operations question, answered from bookings, not from maps.
- **Service quality and operations.** Ratings are used only relative to nearby premium salons;
  fixing a weak lounge's service is a management job, not a location one.

## What it currently says

At the baseline (medium levels: 15-min drive, 60% competitor coverage, 5.5% women in worker
housing, affluence elasticity 0.5):

- **Lounges:** 3 PROTECT (al-ain, al-taif-mall, ras-al-khaimah), 15 HOLD, 5 SHRINK, 1 NOT SCORED
  (the airport lounge serves travellers). **10 of 23** calls are low confidence.
- **The 5 SHRINKs are all Abu Dhabi city lounges** (delma, khaleej-al-arabi,
  mohammed-bin-zayed-city, noya-plaza, westyas): 98-100% of their women are also reached by
  a sibling, and capture is middling to low. One of them (mohammed-bin-zayed-city) flips
  to HOLD in 54 of the 81 assumption combinations. Investigate, don't cut. shahama was a SHRINK
  until the airport lounge stopped counting as its sibling and substitute; it is now a
  low-confidence HOLD, 0.03 above the line. al-maqta was a SHRINK until the rating gap moved from
  the top-k substitutes' median to the whole premium pool's (sanity check SC4); it is now HOLD by
  0.003 (composite 0.353), a knife-edge call flagged low confidence.
- **Growth areas:** 5 GROW (Sharjah, Al Dhaid, Khor Fakkan and Kalba in Sharjah emirate, Al Jerf
  in Ajman; 262k women between them), and 36 WATCH, out of 413 growth areas. The Sharjah four are beyond a 15-minute drive of Bedashing's two Sharjah
  lounges (al-jada, zawaya-walk, both on the Dubai side); why the footprint is only two is a business
  question the model can't answer (licensing, brand fit, landlords). **Al Awir (Dubai)** is a WATCH
  whose size passes only on thin affluence data: 19.4k women, 20.1k addressable, from one DLD area
  (65 villa-heavy contracts) covering 38% of its women, so it is capped at WATCH.
- **Affluence changes no call at medium or strong.** The four big Dubai lounges sit above the 200k
  demand anchor either way; jumeirah-park and zawaya-walk move by under 0.02 and neither crosses a
  line. That is partly by design (see limitations 3): the weighting only reshuffles demand inside
  Dubai, and all 5 SHRINKs are in Abu Dhabi, where it sees nothing.

Treat these as the places to look first, not as answers.

## Run it

Prerequisites: Python ≥ 3.11, [uv](https://docs.astral.sh/uv/) and (optional)
[just](https://just.systems/).

```bash
uv sync --extra dev
uv run streamlit run streamlit_app.py     # http://localhost:8501  (or: just app)
```

No API key needed: the app computes everything in memory from the committed `data/seed/v3/` and
serves the committed AI explanations. `just test` runs the tests. `just labels` prints every
lounge and growth-area call at the baseline as CSV. `just notebook` opens the notebooks (start
with `decisions.ipynb`).

## Using the app

Four pages; the loop is **Overview → click a lounge or area → its page → back**.

1. **Overview** (`/?lounge=delma` or `/?area=kalba-sharjah` preselects): the COO's question, the
   executive summary (answer, ranked arguments, *so what*, *now what*), the at-stake figures, the
   limitations box and the **🧪 What if…?** panel (travel time, competitor coverage, worker-housing
   share, affluence weighting, search recall, close lounges; every call recomputes). Then the map,
   with toggles for growth areas (and SKIPs), Dubai rents, **all catchments (overlap)** and premium
   substitutes (selected lounge or every lounge); click a lounge or area for its short pyramid and
   caveats. **Compare** has a sortable **Lounges** table and a **Growth areas, ranked** table.
2. **Lounges** (`/lounge?lounge=delma`): a picker filtered by emirate checkboxes (Abu Dhabi and
   Dubai ticked; a link ticks its own emirate), then address and rating, the call with its pyramid
   and caveats, raw vs addressable women, the four signals on their scales, premium substitutes,
   which siblings share its women, *What would change the call*, and the factor table (value,
   threshold, meaning, contribution to the composite) with its sources.
3. **Areas** (`/area?area=kalba-sharjah`): a picker of the 68 areas with 5,000+ women, with the
   same emirate checkboxes, then the call against its tests, the margins that would move it, a map
   of its cells, the nearest lounge and the factor table.
4. **How it works & limitations:** the ranked limitations, the market model, every assumption with
   its source, and every constant with why it was chosen.

Links carry the selection, so any page can be shared directly. Guided tour: [`docs/walkthrough.md`](docs/walkthrough.md).

## How it decides

**Market.** Women aged 15+ per ~2 km grid cell (WorldPop 2025 adults, rebalanced so worker housing
counts few women). **Addressable women** weight each cell's women by its median household rent
relative to the women-weighted median (`(rent / median) ^ 0.5` at medium, clipped before
rescaling to a mean of 1 over the observed cells; final weights 0.44-2.53); only
241 Dubai cells have a rent (DLD Ejari), so every other cell weighs 1. A lounge's **catchment** is the cells within a 15-min drive (Mapbox, typical
midday traffic). Its **premium substitutes** are the most-reviewed premium salons in the catchment
that together hold 60% of its premium reviews. **Capture** = the lounge's Google reviews ÷ (its own
+ its substitutes' reviews, scaled up for salons the search missed).

- **One competitive set.** All lounges are treated as one format (same assumed price level, same
  scorecard, each other's substitutes), because we have no data to split them by size, mall vs
  street or menu. The airport lounge gets no call because it serves travellers, not a neighbourhood, and it is left out of every comparison: no lounge's sibling in the overlap, no lounge's premium substitute, no area's nearest lounge. (It used to count as a sibling and a substitute; fixing that moved shahama from SHRINK to HOLD.)
- **Why driving.** The UAE is car-centric: low-density cities on wide arterial roads, malls with
  big car parks, public transport that covers only parts of the cities, and summer heat that
  makes walking to a salon rare. So a drive-time catchment is the honest default; it overstates
  reach for women without a car. Mapbox's typical traffic for a **weekday 12:00** departure is a
  stated simplification: evening rush, when salon demand peaks, is ~40% slower in Dubai (TomTom
  2025), so real after-work catchments are smaller.
- **Why a 0.02° grid.** Cells are ~2.2 x 2.0 km. Cell area varies by under 2% between 24° and
  26°N, where 97% of UAE adults live (2.5% over every cell, 22.9-26.0°N), and nothing computes an
  area in degrees: distances are haversine, sizes are people counts.

**Lounges** (`src/model/scorecard.py`). Four signals, each 0-1 on a *fixed* scale, so a lounge's score
doesn't move when a sibling opens or closes:

| Signal | Measure | 0 at | 1 at | Weight |
|---|---|---|---|---|
| Demand | addressable (affluence-weighted) women 15+ in the catchment | 0 | 200k | 1 |
| Cannibalisation | share of them another lounge also reaches | 100% | 0% | 1 |
| Capture | share of premium-substitute reviews | 0% | 15% | 1 |
| Rating | rating minus the premium pool's median (salons with 20+ reviews) | −0.3★ | +0.3★ | ½ |

PROTECT ≥ 0.65, SHRINK ≤ 0.35, HOLD between: strong calls need the signals to agree. Rating counts
half because Google ratings come in 0.1★ steps. **Low confidence** = within 0.05 of a line, a thin
premium market (under 10 premium salons: the capture score is pulled toward neutral, keeping n/10 of
its distance from 0.5), no rating gap, a call that changes in a third or more (27+) of the 81
combinations of the four assumption levels, or one that changes when a signal weight moves ±25%.

**Growth areas** (`src/model/growth.py`). Populated cells beyond a 15-min drive of every scored lounge,
one area per OSM place name, whether the cells touch or not. Cells with no OSM place within 3 km
(about 34k women) stay in catchments and totals but make no area: nothing actionable is known about
them. **Big enough?** ≥ 20k addressable women, under 50% of adults in worker housing.
**Unsaturated?** Under 150 premium reviews per 1k women in the cells we searched (the lightest quarter
of our own lounges' real premium markets, by a rule fixed in advance; lounge pages show the same
measure). Both → GROW, one → WATCH, neither → SKIP; under 5k women is SKIP, as are areas named
industrial, free zone, military, airport or port, and small unsaturated areas that are mostly worker
housing. Under half the women searched caps at WATCH, as does passing the size test only through
the affluence weighting with rents for under half the women. Each area gets low / medium / high
confidence by its distance from the two lines.

Every anchor, with why it was chosen, is on the app's How page and in `notebooks/decisions.ipynb`.

### Which data answers which question

Field names are as in `src/features/lounges.py`; files are in `data/seed/v3/`.

| Question | Signal(s) | Dataset(s) | How direct |
|---|---|---|---|
| **Q1** protect / hold / shrink a lounge | the composite of the four signals below (`addressable_women`, `shared_share`, `capture`, `rating_gap`) | all of the files below | **Indirect.** Health is a market-position score; there is no revenue or rent (limitations 1) |
| **Q2** where to open | `addressable_women` and `worker_share` per area (big enough?); `premium_reviews_per_1k` (unsaturated?) | `cells.csv` + `emirates.csv` (WorldPop, OSM worker housing), `cell_affluence.csv` (DLD rents, Dubai only), `catchment_cells.csv` (what's already reached), `salons.csv` + `search_circles.csv` (Places) | **Proxy.** Modelled women stand in for customers; premium reviews stand in for competing supply |
| **Q3** overlap with ourselves | `shared_share`: share of a lounge's catchment women another lounge also reaches | `catchment_cells.csv`, `lounge_isochrones.geojson` (Mapbox), `cells.csv` | **Fairly direct** for geography; it can't say where customers would go if a lounge closed (limitations 11) |
| **Q4** strength vs local competition | `capture` (lounge reviews ÷ lounge + premium substitutes), `rating_gap` (rating − median of the catchment's premium salons with 20+ reviews) | `branches.csv` (lounge reviews, rating), `salons.csv`, `lounge_candidates_by_level.csv`, `lounge_search_saturation_by_level.csv` (recall correction) | **Proxy of a proxy** for capture: lifetime Google reviews stand in for customers, which stand in for market share. Rating is direct but coarse (0.1★ steps) |

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
  template. The committed explanations were written in a Claude Code session from the same prompts
  the API would get, not by the API, for the current baseline (with the affluence weighting):
  65 explanations, all passing the grounding check. NOT SCORED and SKIP always use the template.
- **Regenerate** after changing the model or data: `just explain` (API, needs `ANTHROPIC_API_KEY`),
  or offline with `python -m src.explain prompts DIR` → write the answers → `check DIR` → `ingest DIR`
  (see `justfile`).
- **Without it**, the portfolio team would read the factor table and write the memo themselves.
  The layer saves that drafting: it picks the arguments that matter, orders them and turns them
  into board-memo prose with every number checked. It adds no new information; today the text
  mostly restates the factor table in sentences.
- **What it can't see:** anything outside the fact sheet. No P&L, no capacity, no site visits,
  no local knowledge, nothing about why a lounge was opened where it was. The grounding check
  verifies numbers, not adjectives, so a word like "strong" is unchecked.

## How AI was used to build this

Built with **Claude Code** throughout: 119 of the first 149 commits carry a Claude co-author (Opus,
Sonnet and Haiku). Claude wrote the code and tests, the fetch scripts and notebooks, ran
the review passes (the "Fix N" and "review fixes" commits), and wrote the committed explanations
offline in a session from the app's own prompts. The specs and plans it executed are in
`docs/superpowers/`; the audits are `RUBRIC.md` and `SANITY_CHECKS.md`. The human set the
direction and signed off the judgement calls: the scorecard anchors, every paid API run (e.g.
282 Places calls, ~$7) and the ones declined (a ~$54-210 full sweep).

## Data

All committed in `data/seed/v3/`, fetched 2026-10-08/10 by the scripts in `scripts/`. Sources, fetch
dates and caveats: [`data/seed/v3/SOURCES.md`](data/seed/v3/SOURCES.md). What's missing and what
filling each gap would cost: [`docs/data-inventory.md`](docs/data-inventory.md).

| Data | Source | Files |
|---|---|---|
| 24 UAE lounges, Google pin, rating, reviews | Bedashing's store locator + Google Places | `branches.csv` (from `data/seed/lounges.json`) |
| 2,373 ~2 km cells: adults, worker-housing adults | WorldPop 2025, OSM industrial land, Dubai Statistics Center (calibration) | `cells.csv`, `emirates.csv`, `dubai_community_gender.csv` |
| Drive-time catchments, 10/15/20 min | Mapbox isochrones | `lounge_isochrones.geojson`, `catchment_cells.csv`, `cell_isochrones.geojson` |
| Median household rent per DLD area, mapped to 241 Dubai cells (Ejari contracts registered 2026-07-10 to 2026-10-09) | Dubai Land Department open data, downloaded by hand 2026-10-10 (captcha, 3-month cap) | `dubai_rents_by_area.csv`, `cell_affluence.csv` |
| Built form per cell (residential, villa, tower, green shares; height), 2018: tested as a UAE-wide rent proxy and rejected (CV R² −0.10) | EU JRC GHSL R2023A | `cell_built_form.csv` |
| 5,924 salons found (3,833 women's salons kept) around lounges and growth cells | Google Places nearby search | `salons.csv`, `lounge_candidates*.csv`, `growth_salons.csv`, `search_circles.csv` |

Tunable values: [`data/scenarios/baseline.yaml`](data/scenarios/baseline.yaml).

## Why these tools

- **Streamlit**: a data app in plain Python, so whoever maintains the model maintains the UI;
  free hosting on Community Cloud, deployed from `main`.
- **pydeck**: ships with Streamlit (no extra dependency) and returns map clicks into Streamlit's
  rerun model.
- **Mapbox isochrones**: drive times with a traffic model. openrouteservice was tried first: no
  traffic model, and a free quota (~250 a day) that would have taken 3+ days for the 810 cells.
- **Google Places**: ratings, review counts and price levels for every salon. OSM, used in an
  earlier version, has the salons but none of that.
- **uv and just**: a lockfile that reproduces the environment in one command, and one-word recipes.
- **No backend, on purpose.** The data is a committed snapshot, and a what-if recomputes in memory
  in a couple of seconds, so a database or API server would add hosting and moving parts for
  nothing. The price: refreshing data means re-running a script and committing.

## Trade-offs

| Chose | Gave up | Why |
|---|---|---|
| 15-min drive-time catchments (Mapbox, midday) | Straight-line radii; a Huff gravity model | Travel time is what a customer feels; Huff needs a decay rate we have no data to calibrate (it is the listed next step, limitations 5) |
| ~2 km WorldPop grid cells | Official neighbourhoods | OSM neighbourhoods cover 66% of Dubai's women and none of Fujairah |
| Google Places popularity circles (858 calls) | One text search per lounge; OSM | Small circles found 17 of the true top-20 premium salons, one text search 0-2 |
| Capture among premium substitutes covering 60% of reviews | A fixed top-k; splitting every cell among every salon | Comparable across dense and thin markets; ~72-144 calls instead of ~2,100 |
| Lifetime review counts | Reviews per year | Per-year needs a full review scrape, unaffordable and against Google's terms |
| Fixed-scale signals, absolute thresholds | Ranking into thirds (the v1 model) | No forced SHRINKs; a lounge's score doesn't move when a sibling opens or closes |
| Affluence from DLD rents, Dubai only | A UAE-wide built-form proxy | The proxy didn't predict rent (CV R² −0.10); neutral beats wrong |
| Rules decide, Claude explains | An LLM classifier (deleted in v2) | Calls are deterministic and auditable; the AI can only phrase them |
| Explanations written offline in Claude Code | Generating via the API | No API spend; same prompts, same grounding check |
| Search recall 0.66, estimated on one tile | A full sweep of capped circles (~$54-210) | Declined on cost; stated as an estimate and an upper bound |
| Location and market only | Any money: revenue, rent, ROIC | No data; SHRINK means investigate |

## Decisions & hardest parts

**What we solved first, and why.** The plumbing: v0 (2026-09-24 to 26) built the whole loop,
data → features → call → map, on a hand-curated Dubai seed with straight-line catchments, to have
something end to end to critique. In hindsight that was the wrong first problem: the seed had 9
Dubai "branches", 4 of which don't exist. The real data (all 24 lounges, WorldPop, Mapbox, Google
Places) came only on 2026-10-08 to 09, and the model was rebuilt on it.

**What we simplified.** Midday drive times with no distance decay; a cell is in a catchment if its
centre is; lifetime reviews as each salon's draw; capture within the premium end only; Bedashing's
price level assumed; affluence observed in Dubai only; one lounge format; no money and no capacity;
growth areas merged by OSM place name, with cells that have no place within 3 km left out of them.

**How we abstracted.** Space: ~2 km cells carrying women 15+, grouped into drive-time catchments
and, outside them, into growth areas by OSM place name (one per name, contiguous or not). Lounges: four signals on fixed 0-1 scales,
weighted into one composite, cut at 0.35 and 0.65 into three labels. Areas: two yes/no tests
(big enough, unsaturated) into three labels.

**What we trust, and what we don't.** Trusted: lounge locations (Google's pins; the store locator's
were off by up to 16 km), adult population, drive times. Not trusted: absolute capture (lifetime
reviews, an estimated recall correction), Google price levels (36% coverage), the women split
outside Dubai, any affluence outside Dubai. And we didn't trust the AI to make the calls.

**What we automated.** The what-if: every call recomputes in memory, and each lounge's call is
re-run over all 81 assumption combinations to grade confidence. The grounding check on every
explanation, with a template fallback. Fetch caching: every Places and Mapbox response is cached
in `data/raw/`, so the derived files rebuild offline without paying twice. `just labels` exports
the calls.

**What we explain.** Every call: a pyramid (answer, ranked arguments, data points), the factor
table with unit, threshold and meaning, caveats, and how many assumption combinations flip it.
Every assumption with its source (table below), every constant with its reason (How page), and
the limitations, ranked, first.

**What we shipped, and what we didn't.** Shipped: the live app on all 24 lounges in five
emirates, 65 grounded explanations, notebooks per stage, the ranked limitations. Not shipped: any
money or ROIC view, capacity, a free-text question box (the AI only explains precomputed calls),
rush-hour catchments, a full competitor sweep, Bedashing's real price level.

## Repo map

```
streamlit_app.py         entry point; pages in src/webapp/pages/ (overview, lounge, area, how)
src/webapp/              map layers, shared rendering, the what-if panel
src/data_v3.py           loads data/seed/v3/
src/market.py            women 15+ per cell, affluence weight, premium substitutes, capture
src/features/lounges.py  catchments, lounge features, growth areas
src/model/scorecard.py   lounge signals, scales, weights, thresholds, confidence (with the reasons)
src/model/growth.py      GROW / WATCH / SKIP tests (with the reasons)
src/baseline.py          one in-memory run per what-if, and its diff against the baseline
src/explain.py           fact sheets, prioritisation, grounding check, cache, prompts
scripts/                 one-off fetches (Google Places, Mapbox, WorldPop/OSM cells, GHSL, DLD rents)
notebooks/               market_size, catchments, competitors, affluence, features, decisions, explanations, branches
docs/limitations.md      ranked limitations: read first
docs/remaining.md        build log and decision register (historical)
CONTEXT.md               glossary of domain terms
```

Commands: `just app` · `just test` · `just labels` · `just notebook` · `just explain`.

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
| 10 | **How many substitutes** | The most-reviewed premium salons that together hold **60%** of the catchment's premium reviews (50% / 70% as sensitivity): 63 around Al Barsha, 2-3 in Al Dhafra | Reviews are concentrated in thin markets and spread out in dense ones: a fixed top 20 held 22% of reviews around Al Barsha but 66% around Al Taif Mall, so capture against a fixed k meant different things in each catchment. A coverage share makes lounges comparable. (Fixed k = 20 with 10/30 was the earlier design.) | in data |
| 11 | **Competitive set** | Women's beauty, hair and nail salons (Google primary type), found by 576 small-circle popularity searches over the 15-min catchments, plus 282 over the populated growth cells outside them. Men-only (incl. Arabic-named barbers), closed and non-salon places excluded, kept with a reason | No Google search ranks by review count; on a fully swept tile, small popularity circles found 17 of the true top-20 premium salons, one large text search 0-2. Home-service salons, common in the UAE, are invisible: a stated limitation | in data |
| 12 | **Airport lounge** | Gets no call (NOT SCORED), and is left out of every lounge's overlap, substitutes and nearest-lounge | It serves travellers, not a neighbourhood | set |
| 13 | **Female share in worker housing** | Adults in OSM industrial land use are 5.5% female (low 1% / high 15%); every other cell is rebalanced so each emirate's female total is unchanged | Dubai Statistics Center 2022: 13 labour-camp communities are 0.1-27% female (5.5% population-weighted), residential ones 43-54%. Against 21 measured communities, error falls from 0.21 (WorldPop's flat 33.6%) to 0.13. Camps not mapped as industrial in OSM are missed (DIP, very likely Sonapur), so Mirdif-35's market is overstated | in data |
| 14 | **Search recall (estimate)** | Where our search hit Google's 20-result cap, it found **66%** of premium reviews; substitutes' reviews are scaled by 1 + (share of full circles) x (1/0.66 − 1), from 1.03 to 1.39 | Calibrated on one fully swept ~8 km tile around Al Barsha (28.6k of 43.7k premium reviews found). An upper bound (that sweep missed salons too), and it assumes other dense areas behave like Al Barsha. Splitting the full circles instead was costed at ~$54-210 and declined. To be replaced if a full sweep is run | estimate |
| 15 | **Affluence = median household rent** | DLD Ejari contracts for one flat, villa or studio (labour camps, staff housing and bulk leases out), median per DLD area, mapped to cells by name; observed for 241 Dubai cells, neutral (1) everywhere else | Free, official and recent; rent is housing cost, not income or salon spend, and covers 3 months of registrations. A UAE-wide proxy from 2018 built form failed (CV R² −0.10). Abu Dhabi's ADREC data refused queries (HTTP 403); Sharjah publishes none | in data (Dubai only) |
| 16 | **How strongly demand follows rent** | Elasticity 0 (off) / **0.5** / 1: weight = (rent / women-weighted median) ^ e, clipped to 0.25-4 before rescaling to a mean of 1 over observed cells (final weights 0.44-2.53 at 0.5, 0.18-2.68 at 1) | No data ties salon spend to rent; 0.5 says a cell with 4x the median rent counts 2x the women of a median-rent cell, before the rescale that keeps Dubai's observed total. Off reproduces the unweighted model exactly | set |

What these assumptions miss, ranked: [`docs/limitations.md`](docs/limitations.md).
