# App and implementation

Everything about how this was built and how to run it: running the app, how I approached it, how AI
was used to build it, how we checked it, the data, tools, trade-offs, what we'd improve next and a
repo map. The calls come from the [decision model](decision-model.md), their written explanations from
the [LLM explanations model](llm-explanations.md); the overview is the [README](../README.md).

## Running this app

Prerequisites: Python ≥ 3.11, [uv](https://docs.astral.sh/uv/) and (optional)
[just](https://just.systems/).

```bash
uv sync --extra dev
uv run streamlit run streamlit_app.py     # http://localhost:8501  (or: just app)
```

No API key needed: the app computes everything in memory from the committed `data/seed/v3/` and
serves the committed AI explanations. `just test` runs the tests. `just labels` prints every
lounge and growth-area call at the baseline as CSV. `just notebook` opens the notebooks (start
with `scorecard.ipynb`).

## How I approached it

**The framing.** I started from the person who decides: the network and capital owner, who decides
where Bedashing is present and how much capital each site ties up (open, renew, resize, relocate or
exit) and doesn't run the branches. So every call answers "is this a good place for our capital?",
never "is this branch well run?", and each label maps onto a decision they already make: PROTECT,
HOLD or SHRINK at a lounge's lease event, GROW as the start of a site search.

**Three iterations.**
1. **Prove a model is possible from public data:** branch locations and Google ratings ranked into
   simple calls, with a baseline vs scenario loop. It showed the questions could be answered, and
   where the data was too thin.
2. **Build a proper software solution:** rebuilt as a hosted Streamlit app with a real data pipeline
   (population per ~2 km cell, drive times, a competitor pool of about 5,900 salons), in-memory
   what-ifs, grounded AI explanations, tests and a ranked list of limitations.
3. **Refine the model:** demand split among competitors by how much each sells, commercial rent as
   the cost, each site judged within its emirate, decision rules and rent quotes for scenarios, with
   notebooks, sanity checks and a go/no-go rubric guarding each change.

**Key decisions, and their limitations.**
- **Judge each site within its emirate**, against a frozen set of 1,123 competitor salon sites. Dubai
  and Abu Dhabi markets (and rent sources) aren't comparable, and a UAE-wide yardstick sank every dear
  Dubai site. Limitation: a site is only as good as its emirate's yardstick; emirates with under 50 salon
  sites are ranked UAE-wide on demand.
- **Score the site, not how much the lounge itself sells.** Site demand puts a typical lounge (757 reviews,
  4.6★) at each spot, so a strong lounge can't hide a weak site. Limitation: a well-run lounge on a weak
  site still reads SHRINK; its own performance is shown as context.
- **Rent as the cost signal.** It is the cost that differs most between sites (9.5x across our
  lounges) and the one a negotiation can move. Limitation: no revenue, lease or capex, so SHRINK means
  "investigate".
- **Rules decide, AI explains.** Calls must be reproducible and defensible to a board; the AI drafts
  the memo, it never makes the call.
- **A hosted app with no keys.** The decision-maker opens a link; every lounge and area has its own
  URL, so a recommendation can be sent as a link to its evidence. Limitation: the data is a committed
  snapshot, refreshed by re-running scripts.

**What I simplified, and why.** Midday drive times; lifetime Google reviews as each salon's services sold;
one lounge format; no capacity; affluence off (household rents exist only for Dubai, and weighting
by them changes no lounge call). Each is there because the better data is Bedashing's own or not
public; the [decision model](decision-model.md) lists every one with its evidence.

**What I'd do next with Bedashing's data.** Bookings per lounge, to calibrate the demand model
(which today may under-read Dubai) and check the calls; actual leases and P&L, to turn SHRINK into a
return test; chairs and hours, to add capacity; then opening several sites at once and saving named
scenarios side by side ([Potential improvements](#potential-improvements)).

## How AI was used to build this

Built with **Claude Code** throughout: 119 of the first 149 commits carry a Claude co-author (Opus,
Sonnet and Haiku). Claude wrote the code and tests, the fetch scripts and notebooks, ran
the review passes (the "Fix N" and "review fixes" commits), and wrote the committed explanations
offline in a session from the app's own prompts. The audits are `docs/rubric.md` and
`docs/sanity-checks.md`. The human set the
direction and signed off the judgement calls: the scorecard scales and the salon-site reference, every paid API run (e.g.
282 Places calls, ~$7) and the ones declined (a ~$54-210 full sweep).

## How we checked it

- **Sanity checks and back-tests** ([`docs/sanity-checks.md`](sanity-checks.md), re-run and logged after each model change): closing any sibling never pushes another lounge toward SHRINK (23 closures, 0 violations); +50% women in a catchment never lowers its call; 5 of 6 industrial, free-zone and military negative controls come out SKIP (the sixth, mixed-use Dubai Investments Park, is WATCH).
- **Tests:** 196, about 45 s (`just test`); a full baseline run takes about 2-3 s, including: default decision rules reproduce the baseline exactly; a rent quote rescores only that site; tightening the GROW minimum never adds a GROW.
- **Speed guards:** a full baseline run must stay under 8 s warm and 10 s cold (`tests/test_speed.py`).
- **No paid API by accident:** the only paid path must be asked for by name, and a test proves unknown arguments never reach it.
- **What we can't check:** there is no ground truth. Without bookings data the demand model is uncalibrated, so the calls are a ranked shortlist, not a forecast.

## Data

All committed in `data/seed/v3/`, fetched 2026-10-08 to 11 by the scripts in `scripts/`. Sources, fetch
dates and caveats: [`data/seed/v3/SOURCES.md`](../data/seed/v3/SOURCES.md). What's missing and what
filling each gap would cost: [`docs/data-inventory.md`](data-inventory.md).

| Data | Source | Files |
|---|---|---|
| 24 UAE lounges, Google pin, rating, reviews | Bedashing's store locator + Google Places | `branches.csv` (from `data/seed/lounges.json`) |
| 2,373 ~2 km cells: adults, worker-housing adults | WorldPop 2025, OSM industrial land, Dubai Statistics Center (calibration) | `cells.csv`, `emirates.csv`, `dubai_community_gender.csv` |
| Drive-time catchments, 10/15/20 min | Mapbox isochrones | `lounge_isochrones.geojson`, `catchment_cells.csv`, `cell_isochrones.geojson` |
| Median household rent per DLD area, mapped to 241 Dubai cells (Ejari contracts registered 2026-07-10 to 2026-10-09) | Dubai Land Department open data, downloaded by hand 2026-10-10 (captcha, 3-month cap) | `dubai_rents_by_area.csv`, `cell_affluence.csv` |
| Shop rent per m² (the cost signal): Dubai, median AED/m²/yr per DLD area over 13,621 single-unit shop contracts; Abu Dhabi, ADREC 2025 street-retail rates for 111 districts; northern emirates, shop asking rents from 1,206 listings; else the emirate median | DLD open data (same download); ADREC public map, values read by hand 2026-10-11 (its data service refuses queries); Property Finder / Bayut, scraped 2026-10-11 via third-party Apify actors (a grey area under the portals' terms of service) | `dubai_shop_rents_by_area.csv`, `cell_shop_rent.csv`, `adrec_retail_rent_2025.csv`, `listing_rents_clean.csv`, `cell_listing_rent.csv` |
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
| A shop rent as the cost signal, no revenue | Revenue, ROIC | No revenue or lease data; shop rent per m² is the only money in the model. SHRINK means investigate |

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
Every assumption with its source ([decision model](decision-model.md), Assumptions and evidence), every constant with its reason (Decision model page, live values), and
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

## Repo map

```
streamlit_app.py         entry point; pages in src/webapp/pages/: overview (Executive Summary),
                         predictions (What-if explorer), lounge, area, how (the six documentation pages)
src/webapp/              map layers, shared rendering, the what-if panel
src/data_v3.py           loads data/seed/v3/
src/market.py            women 15+ per cell (worker-housing rebalance), which Places results count as
                         women's salons, which competitors count as premium, the search-recall correction
src/model/served.py      Huff served demand, leave-one-out, open-a-lounge what-if
src/features/lounges.py  catchments, lounge features, salon-site reference signals (demand percentile, rent ratio), growth areas
src/model/scorecard.py   lounge signals, scales, weights, thresholds, confidence (with the reasons)
src/model/growth.py      GROW / WATCH / SKIP tests (with the reasons)
src/baseline.py          one in-memory run per what-if, and its diff against the baseline
src/explain.py           fact sheets, prioritisation, grounding check, cache, prompts
scripts/                 one-off fetches and builds (Google Places, Mapbox, WorldPop/OSM cells, GHSL, DLD rents, shop rents)
notebooks/               market_size, catchments, competitors, served_demand, rent, scorecard, growth, branches; features/: affluence, features, decisions, explanations
docs/decision-model.md   the decision model: the ideal model, proxies, steps, diagrams, ignored factors, assumptions
docs/llm-explanations.md the LLM explanations: why, how a pyramid is made and checked, precomputed vs live
docs/app-and-implementation.md   this file: running the app, approach, checks, data, tools, trade-offs, repo map
docs/limitations.md      ranked limitations: read first
docs/glossary.md         glossary of domain terms and decisions
docs/rubric.md, docs/sanity-checks.md   the go/no-go rubric and the sanity checks with their run log
```

Commands: `just app` · `just test` · `just labels` · `just notebook` · `just explain`.
