# Implementation notes

Everything technical that isn't the model itself: the AI layer, how AI was used to build this, the data and where it comes from, why these tools, the trade-offs and what we'd improve next. The model is in [docs/model.md](model.md); the overview is the [README](../README.md).

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
  the API would get, not by the API, for the current baseline, all passing the grounding check. NOT SCORED and SKIP always use the template.
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
offline in a session from the app's own prompts. The audits are `docs/rubric.md` and
`docs/sanity-checks.md`. The human set the
direction and signed off the judgement calls: the scorecard scales and the salon-site reference, every paid API run (e.g.
282 Places calls, ~$7) and the ones declined (a ~$54-210 full sweep).

## The app, page by page

Five pages; the loop is **Executive Summary → click a lounge or area → its page → back**.

1. **Executive Summary** (`/overview`): the portfolio team's question, one governing thought, a *How we measure*
   note (the two proxies and why each threshold sits where it does) and the AI-written summary, then
   three cards (**Review**, **Grow**, **Protect**), each a claim with its share of our served market
   (model estimate). Below them, each card's evidence: a map and a table (composite, share of
   market, out-serves, rent ratio, performance vs its site, confidence; est. growth for areas) whose
   names link to the lounge or area page. Last, **How sure we are**: the HOLDs, the low-confidence
   calls by name, a branch-health KPI box (what each KPI rests on today and the data that would make
   us surer) and the limitations box.
2. **What-if explorer** (`/explore?lounge=delma` or `?area=kalba-sharjah` preselects): the only page
   that reads the what-if. **🧪 Change your decision rules, a rent or the model's assumptions, or test a
   SHRINK** (collapsed at baseline): *Your decision rules* first (demand vs rent weight, PROTECT and
   SHRINK lines, GROW minimum and demand line); the model's assumptions (drive time, competitor
   coverage, worker housing, search recall); *Plug in a quote* (a rent for a lounge or growth area);
   *Test a SHRINK* closes lounges. Once anything differs from the baseline, the **scenario summary**
   appears under the form (Baseline | This scenario | Change: lounge calls, low confidence,
   GROW/WATCH/SKIP, women served, best growth) with **What changed** (~~HOLD~~ → **SHRINK**, with the
   signal that moved). Example: a landlord quote of AED 2,200/m² for City Walk
   (today 4,561) turns it ~~SHRINK~~ → **HOLD** (low confidence; the line is about 2,290); a GROW
   minimum of 10,000 net new women cuts GROW from 34 to 16 areas. Then the map: every area coloured by its call (GROW blue,
   already captured green, WATCH purple, SKIP grey), lounge pins in their call's colour (hollow =
   low confidence), **Jump to** city pills, every lounge's catchment
   always drawn underneath (shared cells red), toggles for premium substitutes (selected lounge or
   every lounge), and a collapsible legend. Click a lounge or area
   for its short pyramid, tests and caveats, and a link to its page.
3. **Lounges** (`/lounge?lounge=delma`): the table of all 24 lounges, filterable by call and
   emirate and sortable, is the picker: select a row and its detail opens below: address and rating,
   the call with its pyramid and caveats, its catchment map, the two signals on their scales,
   *What would change the call* and the factor tree (call, signals, their inputs; scored rows shaded
   red to green), a tab per assumption showing how its estimates and call move, its premium
   competitors table and its shared catchment (which siblings reach its women, and what share they'd
   absorb if it closed).
4. **Areas** (`/area?area=kalba-sharjah`): the GROW and WATCH areas ranked by net new women, the
   same table-as-picker; below, the call with its pyramid and caveats, *How this call was made*
   (the three tests), the factor tree, the per-assumption tabs, a map of its cells and the nearest
   lounge.
5. **README:** the [README](../README.md) (which links to [docs/model.md](model.md) and these
   notes), then live values read from the code each load: every
   assumption with its source and every constant with why it was chosen.

Links carry the selection, so any page can be shared directly. Guided tour: the Walkthrough at the top of the [README](../README.md).

## Data

All committed in `data/seed/v3/`, fetched 2026-10-08/10 by the scripts in `scripts/`. Sources, fetch
dates and caveats: [`data/seed/v3/SOURCES.md`](../data/seed/v3/SOURCES.md). What's missing and what
filling each gap would cost: [`docs/data-inventory.md`](data-inventory.md).

| Data | Source | Files |
|---|---|---|
| 24 UAE lounges, Google pin, rating, reviews | Bedashing's store locator + Google Places | `branches.csv` (from `data/seed/lounges.json`) |
| 2,373 ~2 km cells: adults, worker-housing adults | WorldPop 2025, OSM industrial land, Dubai Statistics Center (calibration) | `cells.csv`, `emirates.csv`, `dubai_community_gender.csv` |
| Drive-time catchments, 10/15/20 min | Mapbox isochrones | `lounge_isochrones.geojson`, `catchment_cells.csv`, `cell_isochrones.geojson` |
| Median household rent per DLD area, mapped to 241 Dubai cells (Ejari contracts registered 2026-07-10 to 2026-10-09) | Dubai Land Department open data, downloaded by hand 2026-10-10 (captcha, 3-month cap) | `dubai_rents_by_area.csv`, `cell_affluence.csv` |
| Shop rent (our site cost): Dubai, median AED/m²/yr per DLD area over 13,621 single-unit shop contracts; Abu Dhabi, ADREC 2025 street-retail rates for 111 districts; northern emirates, shop asking rents from 1,206 listings; else the emirate median | DLD open data (same download); ADREC public map, values read by hand 2026-10-11 (its data service refuses queries); Property Finder / Bayut, scraped 2026-10-11 via third-party Apify actors (a grey area under the portals' terms of service) | `dubai_shop_rents_by_area.csv`, `cell_shop_rent.csv`, `adrec_retail_rent_2025.csv`, `listing_rents_clean.csv`, `cell_listing_rent.csv` |
| Frozen reference of 1,123 premium competitor salon sites: emirate, cell shop rent, women a typical lounge would serve there | Built 2026-10-11 from the committed salons, rents and served model (`scripts/build_site_reference.py`) | `site_reference.csv` |
| Built form per cell (residential, villa, tower, green shares; height), 2018: tested as a UAE-wide rent proxy and rejected (CV R² −0.10) | EU JRC GHSL R2023A | `cell_built_form.csv` |
| 5,924 salons found (3,833 women's salons kept) around lounges and growth cells | Google Places nearby search | `salons.csv`, `lounge_candidates*.csv`, `growth_salons.csv`, `search_circles.csv` |

Tunable values: [`data/scenarios/baseline.yaml`](../data/scenarios/baseline.yaml).

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
| Huff served demand over Mapbox drive-time bands (midday) | Hard catchments; straight-line radii | Travel time is what a customer feels, and Huff splits shared cells instead of counting them twice; its decay is uncalibrated (limitations 2, 5) |
| ~2 km WorldPop grid cells | Official neighbourhoods | OSM neighbourhoods cover 66% of Dubai's women and none of Fujairah |
| Google Places popularity circles (858 calls) | One text search per lounge; OSM | Small circles found 17 of the true top-20 premium salons, one text search 0-2 |
| Capture shown, not scored | Scoring capture beside served demand | Huff already splits each cell by reviews, so scoring capture too double-counted competition |
| Lifetime review counts as the proxy for services sold | Reviews per year | Per-year needs a full review scrape, unaffordable and against Google's terms |
| Fixed-scale signals, absolute thresholds | Ranking into thirds (the v1 model) | No forced SHRINKs; a lounge's score doesn't move when a sibling opens or closes |
| A frozen market of competitor salon sites, per emirate | Scales calibrated on our own 23 lounges; one UAE-wide cost anchor | Our network isn't its own benchmark, and a Dubai contract rent isn't set against a northern asking rent; the reference carries the served model's and the rents' biases (limitations 3, 10) |
| Affluence weighting off | DLD-rent weighting in Dubai; a UAE-wide built-form proxy | Dubai-only weighting changes no lounge call; the proxy didn't predict rent (CV R² −0.10); every woman counting the same beats one emirate on different rules |
| Rules decide, Claude explains | An LLM classifier (deleted in v2) | Calls are deterministic and auditable; the AI can only phrase them |
| Explanations written offline in Claude Code | Generating via the API | No API spend; same prompts, same grounding check |
| Search recall 0.66, estimated on one tile | A full sweep of capped circles (~$54-210) | Declined on cost; stated as an estimate and an upper bound |
| A shop rent as the cost signal, no revenue | Revenue, ROIC | No revenue or lease data; shop rent is the only money (site cost on an assumed unit and fit-out is display only). SHRINK means investigate |

## Decisions and how we worked

**Where we started, and why.** The plumbing: v0 (2026-09-24 to 26) built the whole loop,
data → features → call → map, on a hand-curated Dubai seed with straight-line catchments, to have
something end to end to critique. In hindsight that was the wrong first problem: the seed had 9
Dubai "branches", 4 of which don't exist. The real data (all 24 lounges, WorldPop, Mapbox, Google
Places) came only on 2026-10-08 to 09, and the model was rebuilt on it.

**What runs without a person.** The what-if: every call recomputes in memory, and each lounge's call is
re-run at each of the 27 drive-time x coverage x worker-share combinations to grade confidence
(affluence is off). The grounding check on every
explanation, with a template fallback. Fetch caching: every Places and Mapbox response is cached
in `data/raw/`, so the derived files rebuild offline without paying twice. `just labels` exports
the calls.

**What the product explains.** Every call: a pyramid (answer, ranked arguments, data points), the
factor tree (each scored row shaded by how it pushes the call), caveats, and in how many of the
27 assumption combinations it flips.
Every assumption with its source ([docs/model.md](model.md), Assumptions and evidence), every constant with its reason (How page), and
the limitations, ranked, first.

**What is in the product, and what isn't.** Shipped: the live app on all 24 lounges in five
emirates, grounded explanations, notebooks per stage, the ranked limitations. Not shipped: a
revenue or ROIC view, capacity, a free-text question box (the AI only explains precomputed calls),
rush-hour catchments, a full competitor sweep, Bedashing's real price level.

## Potential improvements

Ideas raised while building this that we haven't acted on, roughly in order of value. The open items in [docs/rubric.md](rubric.md) (*To improve*) and the limitations ([README](../README.md), [docs/limitations.md](limitations.md)) are the detailed record; this is the short list.

**Features**

- **Open lounges in the What-if explorer, several at once.** Today every growth area is evaluated as its own what-if (one typical lounge, net of our lounges and competitors), so the growth percentages can't be added up: neighbouring areas claim the same women (Al Dhaid and Manama). Opening several sites together in the full run would show their *combined* growth, which lounges they take customers from, and which calls move. The model already handles one new site (`what_if_open`); the work is wiring several into `run()`, the map and the tables. Measured cost: a re-run is ~2.7 s, the same as closing a lounge (confidence check ~65%, area what-ifs ~30%), or less if the explorer skips the confidence check. About half a day; add a speed test (two openings < 4 s).
- **Relocation as one move.** Close a lounge and open at a named site in the same scenario (today: close in the explorer, read the area's own what-if separately), so the summary shows the net effect on served women and on the neighbours' calls.
- **Named, saved scenarios side by side.** The explorer holds one scenario per session (assumptions, rules, quotes, closures). Saving them under a name ("City Walk renegotiated", "strict growth bar") and comparing two or three in the summary table would let the portfolio team argue between options rather than against the baseline only. Not built.
- **Choose a portfolio of sites, not a ranked list.** With the above, pick the best *set* of openings greedily (each next site judged net of the ones already chosen), instead of reading down a list whose growths overlap.

**Model and data**

- ~~**Wire drive time and competitor coverage back into the served-demand model.**~~ Done (2026-10-11): drive time sets the decay across the 10/15/20-min bands (10 min = nearest band only, 15 = today's decay, 20 = flatter) and coverage scales the competitors' pull by coverage / 60%, as the old capture did; both are back in the confidence check (27 combinations), the What-if explorer and the per-assumption tabs. `src/model/served.py`, LEVELS_WHY.
- **Check the demand reading against real bookings.** The Huff split reads Dubai as so crowded that a typical lounge at our Dubai sites would serve about 2-5k women, against up to 23k at the best Abu Dhabi sites. Ranking within each emirate keeps that from sinking the Dubai calls, but it still sets every share of our served market and every growth figure. Even a rough ranking of lounges by bookings would confirm it or show the model is under-reading Dubai, and would calibrate the uncalibrated parameters (review exponent, distance decay, outside option).
- **Observed rents where we only have the emirate median.** 17 of 34 GROW areas pass the rent test only because their rent is unknown (scored neutral, low confidence), mostly in Sharjah and the northern emirates. More listings or district rates there would turn those into real calls.
- **Revenue, lease and capex data for a return test.** A return-on-capital gate (rubric OB5) can't be built from shop rent alone; with lease terms and revenue per lounge, SHRINK could mean "losing money" instead of "weak site".
- **Capacity.** Lounges have no capacity in the model (OB2), so "too much capacity in a shared catchment" can't be tested and cannibalisation is shown (siblings' absorbed share), not scored.
- **Thin-market reach.** In small towns a new lounge's 20-min reach covers the next town (Al Dhaid's +35% is mostly Al Dhaid town, also claimed by Manama); treat single large growth figures as a ceiling until reach is checked against real drive times and demand.
- **Score lines.** Percentile scoring bunches lounges in the middle (14 HOLD, 10 within 0.05 of a line). Where PROTECT and SHRINK lines belong is an owner decision, not a tuning job: the What-if explorer's *Your decision rules* lets the owner move them and see the calls move, but the baseline keeps 0.65 / 0.35 until they choose.
- **Better competitor and price data.** A full sweep of the capped search circles (free from 1 November, ~$54-210 before), Bedashing's real price level from its booking pages, and services and price tier per lounge, none of which are in the data today.
- **Affluence beyond Dubai.** Observed household rents exist only for Dubai, so affluence weighting is off; a UAE-wide income or rent proxy would let it back in.

**App polish**

- Lounge and area detail pages, and the AI explanations, still talk in women rather than % of our served market (the explanations need an offline regeneration).
- Composite bars are red even for PROTECT; the "Open →" column is clipped in the Executive Summary's evidence tables; `/overview` shows "Page not found" (the default page lives at `/`).
- Streamlit Cloud has stopped redeploying on push: reboot the app after merging to `main`.
