# Case study gap analysis: what's done, what's missing

Each requirement in `ai-associate-case-study.docx` is checked against the code at `1006f6b`.
Status: ✅ addressed · 🟡 partial · ❌ missing.

> This scorecard is a snapshot of the code **before** the build pass. Competition, opportunity areas, the AI explanation layer, units on tables and the README have since been built. See **Status** below for what's done and what's left.

## Scorecard

### Assignment: the five "at minimum" exploration areas

| # | Requirement | Status | What exists | Gap |
|---|---|---|---|---|
| 1 | Branch locations + branch detail | ✅ | 9 Dubai branches on a pydeck map; click one to see action, rationale, drivers, a feature table, and caveats | Only 9 of Bedashing's 23 UAE branches are covered |
| 2a | Catchments / service radii | 🟡 | Nearest-branch (Voronoi) assignment of 50 community centroids by straight-line distance | No radius and no travel time. The prompt names "precomputed travel-time / catchment data" as an input to source, and none was sourced |
| 2b | Overlap within the competitive set | 🟡 | `contested_share`: the share of a branch's communities whose second-nearest *own* branch is within 1.25× the distance | This only measures overlap with our own branches (cannibalisation). Nothing measures overlap with competitors |
| 3 | Nearby competitors + density/saturation | ❌ | Nothing | No competitor data at all. This is a whole required section |
| 4 | Health indicators + a way to compare branches | 🟡 | A composite of population served, inverted contested share, and rating; a ranked list; the scenario diff | No side-by-side comparison view. The health signal is weak (see the critique below) |
| 5a | PROTECT/HOLD/SHRINK for existing branches | ✅ | `src/model/rubric.py`, plus an optional LLM backend | Problems with how it's defined, covered in the critique below |
| 5b | GROW/WATCH/SKIP for whitespace | ❌ | Nothing. A hypothetical branch added as a scenario gets a PROTECT/HOLD/SHRINK label instead | No candidate areas, no whitespace scoring, no GROW/WATCH/SKIP. This is a whole required section |

### Minimum functional requirements

| Req | Status | Notes |
|---|---|---|
| A. Business framing | 🟡 | Decisions, signals, and the objective are written down. **The decision-maker is still TODO**, and the prompt names that first |
| B. Recommendation logic (coherent, explainable, defensible) | 🟡 | Coherent and explainable. Defensibility is weak: tiers are forced into thirds, and a 0.3★ rating spread carries a full third of the weight |
| C. Geographic reasoning | 🟡 | Proximity, nearest-branch catchments, and sibling overlap are done. Coverage gaps, competitor density, saturation, and travel time are not |
| D. AI-relevant layer | 🟡→❌ in practice | An LLM classifier that redoes the rubric's job. **It is hidden on the public deploy** (no key), so a reviewer opening the live link sees no AI at all. Restating a rubric through an LLM is also close to the "gimmicky" end the prompt warns about |
| E. Explainability (why, which inputs, where to trust) | 🟡 | Rationale, top-2 drivers, caveats, a worked example, and a trust section are all there. Missing: per-input contributions, real confidence (it's hard-coded "medium"), and the automatic "flips at ±X" sensitivity readout (designed, not built) |

### Deliverables

| Item | Status | Notes |
|---|---|---|
| Working product | ✅ | Streamlit app, live on Community Cloud, works with zero config |
| Technical README | 🟡 | Very thorough, but **37 KB, with `> _Fill:_` template prompts and `TODO`s left visible**. The brief says the reviewers are short on time |
| Demo (video, or live link + written walkthrough) | 🟡 | The live link exists. No video and no short written walkthrough |
| Fallback when there's no key | ✅ | Falls back to the rubric automatically |

## Critique beyond the checklist

1. **Two of the five required sections don't exist** (competition, whitespace). A reviewer will check these first. The README's candour about missing them doesn't stand in for having them.
2. **The AI layer can't be seen.** For an *AI Associate* case this is the biggest risk. The fix isn't "set a key on the public deploy". It's an AI layer that can be precomputed and committed (summaries grounded in data), plus a live layer that degrades gracefully.
3. **Forced distribution.** Ranking into thirds always gives 3/3/3. A network where every branch is healthy still produces 3 SHRINKs. That's hard to defend to someone deciding whether to close a branch.
4. **Rating amplification.** Ratings span 4.6 to 4.9. Min-max scaling turns 0.1★ into a 0.33 swing on one third of the score. That's noise driving tiers. `sheikh-zayed-road` has no rating at all, and how it's imputed needs checking.
5. **Scope is Dubai only (9 of 23 branches).** The prompt says a UAE network. It's defensible if argued for, but getting all 23 branches is mostly a data-entry job, not a modelling one.
6. **Catchment is the weakest geographic piece.** The prompt explicitly lists travel time. A precomputed drive-time matrix (communities × branches), committed as a file, would fix this without any runtime dependency.
7. **Stale docs.** The checkboxes in `docs/designs/v1-plan.md` and the Streamlit plan are all unticked even though the code exists. The streamlit-rebuild spec still says "pending implementation plan".
8. **A test times out on cold start.** `tests/webapp/test_pages.py::test_app_loads_without_exception` hits AppTest's 3 s limit on the first run while the baseline self-heals. Also, `uv run pytest` alone fails because pytest is in the `dev` extra.

## Status (updated 2026-10-07, after the build pass)

### Done
- [x] **Competitor seed.** 768 women's beauty/hair salons from OSM (`data/seed/competitors.csv`, via `scripts/fetch_competitors.py`). Queried with a bbox around the communities rather than the AE-DU boundary, which times out on public Overpass. Gents' salons are removed by tag *and* by name: 215 of 984 were men-only, tagged plain `hairdresser`.
- [x] **Competition features.** Each competitor counts toward its nearest community within 3 km. Per branch: competitors in catchment and per 10k women (**competitive overlap**). Per community: count and per 10k.
- [x] **Rubric v2.** Four fixed-scale signals, equal weights, PROTECT ≥ 0.65 / SHRINK ≤ 0.35. Anchors and reasons live in `src/model/rubric.py`. The competition anchor ended up as 15 per 10k → 0 (not 5), because the Dubai median is about 5. Result: 3 PROTECT / 5 HOLD / 1 SHRINK.
- [x] **Missing rating scored neutral** (0.5), with low confidence and a caveat.
- [x] **Opportunity model** (`src/model/opportunity.py`). **Changed from the plan:** "underserved if the catchment branch is heavily cannibalised" was backwards, because cannibalisation means *too much* coverage. An "overloaded branch" rule was tried next and dropped: with 9 branches it labelled 14 of 50 communities GROW. The final rule is distance > 5 km, < 5 competitors per 10k, ≥ 20k women, and worker-housing areas capped at WATCH. Result: 7 GROW, all in Deira / old Dubai / Qusais / Muhaisnah.
- [x] **Map:** opportunity layer (clickable), competitor layer, legend caption.
- [x] **LLM classifier deleted.** Removed the backend setting, toggle, diff fields and tests. The rubric decides; the AI explains.
- [x] **Explanations** (`src/explain.py`): 3 reasons × 2–3 data points, a table caption, and a thresholds note. Grounding check covers cited fields/values *and* every number in the prose; one retry with errors fed back, then template. Cache keyed by a hash of the facts.
- [x] **Units and meanings on every table** (reviewer feedback): a glossary with label, unit and meaning per field. AI-written table captions, with a template caption as fallback. A full glossary on the Model page.
- [x] **ROIC caveat** on the headline and on every branch decision, plus a "what return on capital would need" panel.
- [x] **Framing:** headline, Story page and README name the three audiences and Dubai-only scope.
- [x] **README** rewritten reviewer-first. The old README moved to `docs/history.md`.
- [x] **Test hygiene:** the cold-start AppTest timeout is raised to 30 s; `just test` uses `--extra dev`. 115 tests pass from a cold start; ruff is clean.
- [x] **Stale baseline protection:** `run_meta.json` carries `pipeline_version`, and the app regenerates an older baseline instead of crashing.

### Still to do
- [ ] **⚠️ Generate the AI explanations (placeholder in place).** No API key was available during the build, so `data/explanations/cache.json` is `{}` and the app shows *template* explanations everywhere. To fix: `ANTHROPIC_API_KEY=... just explain`, check how many passed grounding (it prints the count), commit the cache. Until then the brief's "AI layer" requirement is only met in code, not on the live link.
- [x] **Committed and pushed to `main`.** Check that Streamlit Community Cloud redeployed and that the live app shows "7 are GROW" in the headline.
- [ ] **Click through the live app in a browser.** Panels were verified headlessly (AppTest), not visually: the browser extension wasn't connected.
- [ ] **Demo:** a 5–10 min recording, or a written walkthrough. Suggested arc: headline → al-safa-2 SHRINK and why → a Deira GROW area → the scenario that moves al-safa-2 into Deira → the "where not to trust it" section.
- [ ] **Equal-weight weakness:** nad-al-sheba (about 3k women) scores HOLD. Consider a guard rule ("demand score < 0.1 caps the branch at HOLD → flags for review") or keep it and leave the caveat in the README. A judgement call for you.
- [ ] **Optional:** a toggle to shade communities by competitors per 10k (competitor points exist; the choropleth wasn't built).
- [ ] **Optional tidy-up:** the unticked checkboxes in `docs/designs/v1-plan.md` and the Streamlit plan; set the spec status line to implemented.

### Out of scope (deliberate)
Travel time and isochrones · expanding to all 23 UAE branches · analyst chat with tools · per-scenario re-acquire · a side-by-side comparison view · a "flips at ±X" sensitivity readout.

## Decisions

Settled in a grilling session on 2026-10-07.

| # | Decision | Answer |
|---|---|---|
| D1 | Time budget / deadline | 3 days. Travel time and the 23-branch expansion are out |
| D2 | Audiences | The tool supports the conversation between three roles. **Primary user:** Bedashing's portfolio/network team, who form recommendations. **Decision-maker:** the COO, who approves or questions them and is accountable for operations and ROIC. **Board:** the PE board, who must be persuaded. Effect on the UI: the headline is conclusion-first for the COO; the map, scenarios and drill-down are for the portfolio team; explanations are written in board-memo tone (claim, evidence, caveat). **Consequence for ROIC:** the tool covers the location and market side of ROIC only. The capital side (revenue, rent, capex) has no data, and the app has to say so wherever ROIC is mentioned |
| D3 | Geographic scope (Dubai vs. UAE) | Dubai only, stated as a deliberate scope choice in both the README and the app |
| D4 | Competitor data source | OSM (Overpass) |
| D5 | Whitespace candidate unit | The existing 50 communities |
| D6 | Shape of the AI layer | A generated explanation for each decision: 3 supporting reasons, each with 2–3 supporting data points |
| D7 | Tiering: forced thirds vs. thresholds | Absolute thresholds. The generated explanation states the thresholds and briefly says why they were chosen |
| D8 | Catchment method | The simplest option: straight-line nearest branch, as already built. Not chasing correctness |
| D9 | Overlap terms | Cannibalisation (own branches) and competitive overlap (rivals) are separate signals. Competitive overlap gets added as its own feature |
| D10 | Fixed scales for thresholds | Fixed anchor values for each signal (see Day 1). Claude proposes the anchors with written reasons, and the user can veto |
| D11 | "Nearby competitor" | Each competitor is assigned to its nearest community, then totalled per catchment. No radius |
| D12 | Competitive set | OSM `shop=beauty` and `shop=hairdresser`, excluding barbers |
| D13 | Does competitive overlap move the action? | Yes: a 4th equal-weight signal |
| D14 | Opportunity action rule | 2×2 of underserved (nearest branch > 5 km) × unsaturated (< 5 competitors per 10k), with a 20k-women floor and worker-housing areas capped at WATCH |
| D15 | How explanations are generated | Haiku with forced tool output and a grounding check. Baseline explanations are committed. Without a key, a labelled template is used |
| D16 | LLM classifier | Deleted |
