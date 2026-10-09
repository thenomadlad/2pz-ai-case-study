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
