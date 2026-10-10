# Case Study Rubric

Our **go/no-go criteria**: the checklist that grades our solution against the brief in `ai-associate-case-study.docx`. Every requirement in the brief maps to at least one item here. The traceability table at the bottom shows where.

**How to use it:** this is our own working checklist, and we make repeated passes over it. Tick an item only when the solution clearly meets it. "It kind of does this" doesn't count. Leave the box open and add the gap under that section's *To improve* list, with the item ID (e.g. `- E3: no per-cell driver breakdown`). Strike or delete an entry once it's fixed.

**Tags:** `[brief]` means the item is stated in the brief or directly implied by it. Failing one is a real gap against the assignment. `[ours]` means it's our own quality bar. Failing one is a judgement call: fix it if it's cheap or if it makes a `[brief]` item stronger, and otherwise park it. Part 7 is all `[ours]`.

**Go / no-go.** The solution is **GO** (ready to submit) only when all three hold:
1. Every `[brief]` item is ticked.
2. Every `[ours]` item is either ticked or parked, with a `parked:` reason in its To-improve list.
3. The latest run of [`SANITY_CHECKS.md`](SANITY_CHECKS.md) has no unexplained failure. That file holds the user stories, back-tests and sanity checks, which are about whether the answers are *believable* rather than whether a box exists.

Anything else is **NO-GO**, and the audit log records which condition failed.

## Audit log

| Pass | Date | `[brief]` | `[ours]` (Parts 1–6) | Part 7 | Verdict | Headline |
|---|---|---|---|---|---|---|
| 1 | 2026-10-10 | 37/80 | 17/40 | 5/26 | **NO-GO**: 43 `[brief]` items open, nothing parked, sanity checks not yet run as a set | Brief coverage is solid on data, explainability and the AI layer. The model has no capacity, served-demand or ROIC concept (OB1–OB5), so 1.4, 2.5, 3.6, E6, US4/US5/US7 fail together, and the back-test shows the growth rule calls our own lounges saturated (MO5). There's no demo or walkthrough, and the docs are stale. |


---

## Part 1: The five business questions

These are the product's reason to exist. Part 2 (layers), Part 3 (functional requirements) and Part 4 (data sourcing) all serve these.

### Q1. Which existing branches should we protect, hold, or shrink?

- [x] `[brief]` **1.1 Every branch gets a label.** No branch in the network is missing one. The label set (PROTECT / HOLD / SHRINK, or our own) is defined in one place.
- [ ] `[ours]` **1.2 Labels mean an action.** Each label is defined as what leadership should *do*, e.g. "SHRINK = reduce footprint/staff or consolidate into X". A score band alone isn't a definition.
- [x] `[ours]` **1.3 The inputs combine all four lenses:** branch health (Q4), local competition (Q4), self-overlap (Q3) and catchment demand (Layer 2).
- [ ] `[ours]` **1.4 Overlap affects labels only through cannibalization (3.6).** Overlap on its own is never a penalty. A branch moves toward SHRINK only when its capacity exceeds the demand it can reach once shared with our other branches. Overlap that's drawn on the map but has no defined effect on labels fails this item.
- [ ] `[ours]` **1.5 Thresholds are justified.** Every cut-off and weight has a written reason: data-driven, a business rule, or an explicitly stated judgement call.
- [x] `[ours]` **1.6 The distribution makes sense.** The label counts are reported. If one label dominates, there's an explanation, and the model isn't simply defaulting to HOLD.
- [ ] `[ours]` **1.7 Stability is checked.** We know which branches flip labels under reasonable changes to weights or thresholds, and borderline cases are flagged as such.
- [x] `[brief]` **1.8 Branch-level drill-down.** From any branch you can see its label, the drivers behind it, its raw inputs and its caveats (see E1–E4).

*To improve:*

- 1.2: only SHRINK has an action ("investigate, not close", CONTEXT.md:86). PROTECT and HOLD are just score bands (scorecard.py:46-50). Write the action for each.
- 1.4: cannibalisation is `shared_share`, i.e. any overlap (features/lounges.py:143), with no notion of capacity. All 7 SHRINKs are Abu Dhabi lounges with 87–100% shared. Blocked on OB3.
- 1.5: the equal 1/1/1/0.5 weights are never argued.
- 1.7: flips are counted over 81 combinations of assumption levels only. The scorecard's own weights, anchors and the 0.65/0.35 lines are never varied.


### Q2. Where should we consider opening new branches?

- [x] `[brief]` **2.1 The candidate universe is defined.** Areas, grid cells, hexes or districts, with a stated reason for the unit and its resolution.
- [ ] `[brief]` **2.2 Every candidate gets a label** (GROW / WATCH / SKIP or our own), and each label means an action.
- [ ] `[ours]` **2.3 Demand side:** a population or affluence proxy, plus a target-customer fit signal.
- [x] `[brief]` **2.4 Supply side:** competitor density or saturation within the candidate's catchment.
- [ ] `[brief]` **2.5 Our own coverage:** distance or travel time to our nearest branch. Whitespace means *unserved demand* (OB3), not "outside our catchments". An under-served area inside our footprint can still be GROW, and an area outside it can be SKIP if competitors already serve it.
- [x] `[ours]` **2.6 SKIP actually happens.** The model rules areas out with a stated reason. A model that only says GROW or WATCH is hedging.
- [x] `[ours]` **2.7 WATCH has a meaning.** It says what would move an area to GROW or SKIP, e.g. "rent data missing" or "demand is OK but saturation is borderline".
- [ ] `[ours]` **2.8 Ranking.** Within GROW, candidates are ordered so leadership has a top N, not just a set.
- [ ] `[ours]` **2.9 Geographic realism.** Candidates are reachable, inhabited places. Desert, sea, industrial zones and airports are not proposed unless that's intended and justified.

*To improve:*

- 2.2: GROW and WATCH are defined as test outcomes, not actions (GROW's own text says "verify before opening").
- 2.3: the affluence weight applies only where rent is observed (241 Dubai cells) and is neutral everywhere else. There is no target-customer signal outside Dubai.
- 2.5: areas are by construction only cells no lounge reaches (lounges.py:154), so under-served demand inside the footprint can never be GROW. Blocked on OB3.
- 2.8: there is no ranked top N. The summary lists the 4 GROWs alphabetically and the picker sorts by women.
- 2.9: industrial and military areas reach WATCH (jabal-ali-industrial-3, dubai-investments-park, jebel-ali-north-free-zone, zayed-military-city, among others) because the worker-housing cap only applies to big areas.


### Q3. Where are we overlapping with ourselves?

- [x] `[brief]` **3.1 Overlap is measured,** as catchment intersection area, shared population, or travel-time overlap. "Two pins are close" isn't a measurement.
- [x] `[ours]` **3.2 Pairwise view.** You can see which branch pairs overlap and by how much.
- [ ] `[brief]` **3.3 Same competitive set.** Overlap is only counted between branches that compete for the same customer (same format, tier or service mix), as the brief asks. Any simplification is stated.
- [ ] `[brief]` **3.4 It's visible on the map** as overlapping catchments or highlighted pairs.
- [ ] `[ours]` **3.5 It feeds decisions** into Q1 (SHRINK or consolidate when capacity in the shared zone is excess) and Q2 (a new site's demand is counted net of the capacity already reaching it).
- [ ] `[ours]` **3.6 Cannibalization is defined, not assumed.** Overlap counts as cannibalization only when demand in the shared zone is less than the combined capacity reaching it (OB3). Overlap where demand is high is legitimate density, and it also keeps competitors out. The definition lives in one place in the code and docs, and it's the only route by which overlap changes a label.

*To improve:*

- 3.3: "all lounges are one competitive set" is only implicit. State it.
- 3.4: the map draws one lounge's catchment at a time (map.py:77). There is no overlap layer and no highlighted pairs.
- 3.5: Q2 drops reached cells instead of netting out the capacity already reaching them.
- 3.6: there is no capacity concept, so overlap is never compared with demand. Blocked on OB2/OB3.


### Q4. How strong or weak is each branch relative to local competition?

- [x] `[brief]` **4.1 Branch health signals:** ratings, review volume, review recency or trend, or other performance proxies. Each one names its source and date.
- [x] `[brief]` **4.2 Relative, not absolute.** Each branch is compared with the competitors in *its* catchment (e.g. rating percentile among local salons), not only with a network-wide average.
- [x] `[brief]` **4.3 Competitive density indicators:** a count and/or per-capita measure of competitors in each catchment.
- [ ] `[brief]` **4.4 Saturation indicator:** a supply-vs-demand measure such as salons per 10k population or per unit of spend.
- [x] `[ours]` **4.5 Competitor definition.** What counts as a competitor (category, tier, minimum review count) is written down, and noise like barbers or nail-only shops is handled deliberately.
- [ ] `[ours]` **4.6 Small-sample handling.** A 5.0 rating from 3 reviews is not treated as equal to 4.6 from 900. We use shrinkage, a minimum-n rule or a flag.
- [ ] `[brief]` **4.7 A comparison method.** There's a side-by-side view, a ranking or a scorecard across branches on common axes.

*To improve:*

- 4.4: reviews per 1k women exists for areas only. Lounges get no saturation figure (it isn't in LOUNGE_TABLE, explain.py:287).
- 4.6: small samples are handled only implicitly. The al-dhafra rating median uses a 26-review salon. Add a minimum-n rule or shrinkage.
- 4.7: the app has no cross-lounge comparison table. It exists only in decisions.ipynb.


### Q5. How can decision-makers explore these answers visually and interactively?

- [ ] `[brief]` **5.1 Map-first overview:** branches, competitors, catchments and opportunity areas on one map, with toggleable layers.
- [x] `[brief]` **5.2 A drill-down page** for each branch and each opportunity area.
- [ ] `[ours]` **5.3 Filters and sorting** by label, score, area or emirate.
- [x] `[ours]` **5.4 Legends and labels** let a non-technical exec read the map without being told what the colors mean.
- [ ] `[ours]` **5.5 What-if or scenario control** (e.g. adjust weights or thresholds and see labels change). Nice to have, but it directly supports "defensible".
- [x] `[ours]` **5.6 The AI layer is reachable from the UI** (see D). It isn't hidden in a notebook.
- [ ] `[ours]` **5.7 It works on a reviewer's screen.** Reasonable load time, and nothing breaks at a laptop window size.

*To improve:*

- 5.1: catchments and competitors show only for the selected lounge.
- 5.3: there's no filter or sort by label, score or emirate.
- 5.5: the what-if covers assumption levels, recall and lounge closures. It can't change weights or thresholds.
- 5.7: the overview renders in 1.9 s in AppTest, but nobody has checked it visually at laptop width.


---

## Part 2: Required layers (minimum explorable content)

The brief lists these as the minimum content of the product. Most of the substance is covered in Part 1, so this part checks that each layer is present and explorable.

- [ ] `[brief]` **L1. Current branch network:** branch locations ✔ branch-level detail (address, rating, reviews, services or tier, label) ✔ → see Q1.8, Q5.2
- [ ] `[brief]` **L2. Catchment / coverage:** catchment areas or service radii ✔ overlap between branches in the same competitive set ✔ → see Q3
- [ ] `[brief]` **L3. Competition:** nearby competitors ✔ density or saturation indicators ✔ → see Q4.3–4.5
- [ ] `[brief]` **L4. Performance / health:** quality or performance indicators ✔ a method for comparing branches ✔ → see Q4.1, 4.2, 4.6, 4.7
- [x] `[brief]` **L5. Decision layer:** model for existing branches ✔ model for whitespace ✔ → see Q1, Q2

*To improve:*

- L1: the address (it's in branches.csv) and services/tier are not shown.
- L2: see 3.4. L3: only premium substitutes are shown, and lounges have no saturation figure (see 4.4). L4: see 4.7.


---

## Part 3: Minimum functional requirements (A–E)

### A. Business framing

- [x] `[brief]` **A1. Decision-maker named:** who they are (e.g. Head of Network / portfolio team / CEO) and what they care about.
- [ ] `[brief]` **A2. Decisions enumerated:** the specific decisions, each tied to a label set, e.g. "approve lease renewal → PROTECT/HOLD/SHRINK".
- [ ] `[brief]` **A3. Metrics that matter:** the north-star metric (services delivered, OB1) and the proxies standing in for it are named. Each signal is listed with *why* it matters for the decision, not just *that* we computed it.
- [ ] `[brief]` **A4. How the system supports the decision:** the flow from question to screen to evidence to action is stated.
- [ ] `[ours]` **A5. Out of scope** is stated: actual P&L (we only model contribution from assumptions, see OB5), in-branch staffing, quality management and operations, and anything else we deliberately don't model, with the reason. Our job ends once capacity is allocated to sites (OB4).
- [ ] `[ours]` **A6. Framing shows up up front:** in the README and the demo opening, not only in a design doc.
- [ ] `[ours]` **A7. The first page leads with the business.** The overview opens on the COO's question and the headline answer (e.g. "N lounges to protect, M under pressure, top 3 openings, and what's at stake") before any map layer or score. Someone who reads only the first screen should know what to do next.

*To improve:*

- A2: there's no mapping from decision to label (e.g. lease renewal → PROTECT/HOLD/SHRINK, site search → GROW, revisit in N months → WATCH).
- A3: the north star (services delivered) and its proxy are never named. `est_customers` is computed but unused.
- A4: no flow is stated from question to screen to evidence to action.
- A5: the only out-of-scope list (docs/remaining.md:81) is stale and lists things that are now built. Write one in the README covering P&L, staffing and ops, and saying our job ends at the site.
- A6: there's no demo and no walkthrough (see M1).
- A7: the headline exists ("Protect three lounges, investigate seven, open in four Sharjah-area growth areas…"), but the COO's question is never stated, the stake is counted in women only, and the SHRINKs have nothing at stake.


### B. Recommendation logic

The brief says it must be **coherent, explainable, defensible**. It does not have to be mathematically perfect.

- [ ] `[brief]` **B1. Coherent:** the same inputs give the same outputs, labels are mutually exclusive, there are no contradictions (e.g. the best-rated, least-overlapped branch marked SHRINK without a stated reason), and the branch and whitespace models share their definitions (same catchment, same competitor set).
- [x] `[brief]` **B2. Explainable:** the logic fits on one page (rules, score formula, decision tree) and a non-technical reader could follow it.
- [ ] `[brief]` **B3. Defensible:** every weight and threshold has a rationale (see 1.5), the method choice is justified against at least one alternative we considered, and we've sanity-checked the output against local knowledge or spot checks.
- [x] `[brief]` **B4. Covers both populations:** existing branches *and* opportunity areas.
- [x] `[ours]` **B5. Tested:** unit tests pin the classification rules, and a regression check catches unintended label changes.
- [ ] `[ours]` **B6. Reproducible:** one command rebuilds the scores and labels from the sourced data.

*To improve:*

- B1: the lounge and growth models use different demand units (a 15-min catchment vs. OSM-name pieces) and different competition measures (capture vs. reviews per 1k), and the back-test shows they disagree (see MO8).
- B3: the weights are never argued. Estimated customers was rejected partly because it "turned four of the five Dubai lounges into SHRINK" (see MO7).
- B6: no command writes the scores and labels to a file. The seed data is rebuilt by several one-off scripts.


### C. Geographic reasoning

The brief asks us to use geography *meaningfully*. Each item below should both exist and affect a recommendation.

- [x] `[brief]` **C1. Catchments,** preferably travel-time based (isochrones). Radii are acceptable with a stated reason.
- [x] `[brief]` **C2. Proximity:** distance or time to competitors and to our own branches.
- [ ] `[brief]` **C3. Overlap:** see Q3.
- [x] `[brief]` **C4. Coverage gaps:** populated areas outside our catchments are identified, and that feeds Q2.
- [x] `[brief]` **C5. Competitor density:** see Q4.3.
- [ ] `[brief]` **C6. Market saturation:** see Q4.4.
- [ ] `[brief]` **C7. Travel-time logic,** with the drive-time mode and minute threshold stated and justified for UAE car-centric travel.
- [ ] `[ours]` **C8. Spatial unit and CRS are sound:** areas are computed in a metric projection, not raw degrees, and the cell size is justified.
- [x] `[brief]` **C9. Geography changes outcomes.** At least one example shows a label that is *because of* a spatial factor (overlap, gap, saturation).

*To improve:*

- C3: overlap isn't on the map, and it takes no account of capacity (see 3.4, 3.6).
- C6: lounge catchments have no supply-vs-demand saturation measure.
- C7: driving as the mode is never argued for the UAE, and midday rather than rush hour is only flagged.
- C8: the 0.02° grid is in degrees with haversine distances, and its resolution isn't justified. Add a line: cell area varies by under 2% at 24–26°N, and nothing computes area in degrees.


### D. AI-relevant design

The brief says the AI layer must be practical, not gimmicky.

- [x] `[brief]` **D1. At least one meaningful AI layer.** Possible kinds: NL interaction, AI-assisted explanation, grounded summaries, a tool-using analyst, prompt/tool/retrieval design, or an agentic flow. Name the one we chose.
- [x] `[brief]` **D2. Grounded:** AI output is generated from our computed data, so every number it states can be traced to a field. No invented facts.
- [x] `[ours]` **D3. Groundedness is verified:** there's an automated check or a documented review showing outputs match the data.
- [ ] `[brief]` **D4. Practical value:** the layer saves the decision-maker time or adds insight the raw table doesn't. We can say what a user would do without it.
- [x] `[ours]` **D5. The AI explains the model, it doesn't make the decisions.** If labels come from deterministic logic and the AI only narrates them, we say so as a trust choice.
- [x] `[ours]` **D6. Prompt and design are visible:** the prompt or tool schema is in the repo, along with why we designed it that way.
- [x] `[brief]` **D7. Failure modes are handled:** no API key, rate limits, stale cache. An offline or cached mode keeps the product working (see Part 5).
- [ ] `[brief]` **D8. Responsible use:** limitations of the AI layer are stated (hallucination risk, what it can't see), and so is how AI tools were used to *build* the solution.

*To improve:*

- D3 (passes, but harden): a cache hit is served without re-verifying. Add a test that every committed cache entry passes `verify()`.
- D4: the docs never say what a user would do without the layer, and the outputs mostly restate the factor table (see E6).
- D8: nothing says how AI tools built the code, data and reviews. There's little on what the AI can't see.


### E. Explainability

From the reviewer's seat, each question below should be answerable **for any single branch or area, in the product, in under a minute**.

- [x] `[brief]` **E1. "Why did this branch get this recommendation?"** Per-branch rationale: which rule or threshold fired, and the input values that triggered it.
- [x] `[brief]` **E2. "Why is this area attractive or unattractive?"** Per-area rationale, both its demand and its supply side, including why it's *not* GROW when it's WATCH or SKIP.
- [ ] `[brief]` **E3. "Which inputs most influenced the outcome?"** Per-entity input attribution: contribution breakdown, rank of drivers, or a counterfactual ("would be GROW if saturation < X"). Saying which rule fired doesn't answer this. We need magnitudes or ordering.
- [ ] `[brief]` **E4. "Where should we trust the model, and where should we be careful?"**
  - [x] Global: a limitations doc covering data gaps, proxies, biases and staleness.
  - [ ] Per entity: confidence or caveat flags on the specific recommendation (missing data, low review count, imputed values, borderline score).
  - [x] Known failure cases are named, with examples.
- [ ] `[ours]` **E5. Consistency:** the explanation and the label never disagree, and an automated test enforces it.
- [ ] `[ours]` **E6. What / so what / now what.** Every recommendation, whether in the generated text, the UI or the demo, answers all three:
  - **What:** the label and the two or three facts behind it, with numbers.
  - **So what:** the business consequence in the COO's terms, i.e. services and demand at stake, the competitive position, and whether it clears the ROIC gate (OB5).
  - **Now what:** the action leadership should take, and what would change the call.

  "GROW because the demand score is 0.8" fails this item. A factor-level explanation alone is a *what* without a *so what*. The prompt for generated text has to require all three parts, and a spot check of generated outputs confirms it does.

*To improve:*

- E3: there's no contribution column (w·s/Σw) and no counterfactual (e.g. "HOLD if shared_share < X"). Area topics come in a fixed order with no gap-to-line figure.
- E4-entity: areas have caveats but no confidence grade.
- E5: `verify()` never checks the label wording in the prose. 0 of 65 contradict their label today, but nothing enforces it.
- E6: the prompt (explain.py:568) asks for a pyramid but never a so-what or a now-what, and it forbids talking about money. Only 17 of 65 explanations say what would change the call. Example of a bare "what": "GROW Kalba: 23,464 women and a premium market under the 50-review line make it a lounge candidate." Fix: add `so_what`/`now_what` schema fields, a `verify` rule, and flip thresholds in the fact sheet, then regenerate offline.


---

## Part 4: Data sourcing

The brief says to source inputs from public sources and lists some combination of these.

- [x] `[brief]` **S1. Branch location data,** with its source.
- [x] `[brief]` **S2. Ratings / review signals,** with source and pull date.
- [x] `[brief]` **S3. Competitor data,** with source, query definition and coverage.
- [x] `[brief]` **S4. Precomputed travel-time / catchment data,** with the provider and parameters.
- [x] `[ours]` **S5. Further context data** (population, affluence, rent, etc.), each with a stated reason for inclusion.
- [ ] `[ours]` **S6. Data inventory:** source, date, licence or ToS, row counts and known gaps for every dataset.
- [ ] `[ours]` **S7. Provenance in the product:** a reviewer can tell where a number came from.
- [x] `[ours]` **S8. Proxy honesty:** wherever we use a proxy (e.g. reviews standing in for revenue), the gap between proxy and truth is stated.
- [x] `[ours]` **S9. Fetch scripts are reproducible**, or the committed snapshots are explained if re-fetching needs paid keys.

*To improve:*

- S6: docs/data-inventory.md is stale. It says 4,237 salons when there are 5,924, has no DLD/GHSL rows, and has no licence/ToS column (OSM ODbL, Mapbox storage terms, GHSL).
- S7: provenance appears only on the How page. The lounge and area factor tables have no source or date.


---

## Part 5: Deliverables and submission

### Working product

- [ ] `[brief]` **P1. Usable end to end:** a reviewer can go from overview to a recommendation to its explanation without help.
- [ ] `[brief]` **P2. The format is justified:** why a web app, notebook, agent or whatever we picked suits this decision-maker.
- [x] `[brief]` **P3. Easy to run:** one or two commands, or a hosted link.

### Technical README

- [ ] `[brief]` **R1. Setup and run instructions** that work on a clean machine, verified.
- [ ] `[brief]` **R2. Written for time-constrained reviewers:** a TL;DR at the top, the live link first, and a "what to look at in 5 minutes" path.
- [ ] `[brief]` **R3. Architecture and tech-stack rationale:** why these tools.
- [x] `[ours]` **R4. Pointers** to the framing (A), logic (B), limitations (E4) and data inventory (S6).

### Demo

- [ ] `[brief]` **M1. One of:** a 5–10 minute recorded walkthrough, **or** a live hosted version plus a short written walkthrough.
- [ ] `[ours]` **M2. It covers** framing → the map → a branch decision with its explanation → an opportunity with its explanation → the AI layer → limitations.
- [ ] `[brief]` **M3. If recorded, it fits in 5–10 minutes.**

### Secrets and paid APIs

- [x] `[brief]` **K1. A fallback mode** exists for anything needing secrets or paid APIs, and the product works without keys.
- [x] `[brief]` **K2. Otherwise, screenshots or a recording** show the paid path working.
- [x] `[ours]` **K3. No secrets** are committed to the repo.

### Submission bundle

- [x] `[brief]` **U1.** Link to the source repository
- [x] `[brief]` **U2.** README with run instructions
- [ ] `[brief]` **U3.** Demo video or live link

*To improve:*

- P1: no browser click-through of the live app has been recorded (remaining.md:73).
- P2: nothing says why a web app suits the COO.
- R1: the README says 135 tests when 136 collect. It lists no prerequisites (uv, just, Python ≥3.11) and hasn't been verified in a fresh clone.
- R2: there's no 5-minute path. Add 4–5 guided steps that name specific lounges and areas.
- R3: the README has no tech-stack rationale. The only one is in the stale history.md.
- M1–M3: there's no walkthrough and no video (history.md:476 is still a TODO). It should follow the M2 arc.
- U3: only the live link exists, and it needs a written walkthrough alongside it.
- K2 (note): the paid explanation path has never been exercised, and no test mocks the API client.


---

## Part 6: Constraints and how we're judged

### Constraints we're allowed to lean on, as long as we use them deliberately

- [x] `[brief]` **X1. Simplifications are explained.** Every simplification ("you may simplify parts of the problem if you explain why") is listed with its reason and its cost.
- [ ] `[brief]` **X2. Static files instead of a backend** is a stated choice, if we made it.
- [x] `[brief]` **X3. No time spent on irrelevant production polish.** Anything production-grade we built has to materially improve the case.

### Evaluation lenses

The brief says *"this is not a coding test"*. Each lens needs a visible artifact.

- [x] `[brief]` **J1. Problem framing:** see A.
- [x] `[brief]` **J2. Research:** how we found and vetted the data and the domain assumptions (see S6, design docs).
- [x] `[brief]` **J3. Solution structure:** pipeline stages are clear (sourcing → features → model → explain → UI).
- [ ] `[brief]` **J4. Tech-stack decision:** see R3.
- [ ] `[brief]` **J5. Trade-offs:** a written list of what we chose, what we gave up and why.
- [ ] `[brief]` **J6. Responsible and effective AI use:** see D8, covering both AI in the product and AI in the build.
- [ ] `[brief]` **J7. Usable delivery:** see P1–P3.

### The closing "hardest part" questions

Each should have a one-paragraph answer somewhere a reviewer will find it, such as the README or a decisions doc.

- [ ] `[brief]` **H1.** What problem did we solve first, and why?
- [ ] `[brief]` **H2.** What did we simplify?
- [ ] `[brief]` **H3.** How did we abstract (the spatial unit, scores, labels)?
- [ ] `[brief]` **H4.** What did we trust, and what didn't we?
- [ ] `[brief]` **H5.** What did we automate?
- [ ] `[brief]` **H6.** What did we explain?
- [ ] `[brief]` **H7.** What did we ship, and what didn't we?

*To improve:*

- X2: running from static files in memory is stated as a fact, not as a choice.
- X3 (passes, but): .devcontainer is unused boilerplate that turns off CORS and XSRF. Delete it or justify it.
- J4: see R3. J5: there's no current "chose / gave up / why" table; history.md:421 describes the old model. J6: see D8. J7: see P1 and R1.
- H1–H7: there's no "Decisions & hardest parts" section. H1 and H5 aren't answered anywhere; the others are scattered across the README and limitations.
- Stale docs contradict the current model: designs/v2.md, remaining.md (out-of-scope and to-do lists), history.md (`_Fill:_`/TODO prompts), and the comment at tests/webapp/test_pages.py:55. Prune them or add staleness banners.


---

## Part 7: Our standards for data and modeling

Parts 1–6 ask whether we did what the brief asked. This part asks whether the thing underneath is any good. All items here are `[ours]`.

### Objective: services delivered, not branches

- [ ] **OB1. The objective is services delivered,** meaning demand served by our capacity. It isn't branch count, and it isn't a branch's own score. Within the ROIC gate (OB5), every label traces back to it: PROTECT = capacity serving demand we'd otherwise lose; SHRINK = capacity in excess of the demand it can reach; GROW = demand that no capacity (ours or a competitor's) serves well.
- [ ] **OB2. A branch is modeled as a bundle of capacity** (specialists × hours, which we can't observe directly). The capacity proxy is named (e.g. review volume as throughput, unit size, listed specialists), its weakness is stated, and there's an equal-capacity fallback if no proxy holds up.
- [ ] **OB3. Demand and capacity share a spatial frame.** Demand per cell and capacity spread across cells through catchments, so served vs. unserved demand can be computed per cell. This is the Huff / IRS logic from MO4, so it should be built once and used by both models.
- [ ] **OB4. Scope ends at the site.** We decide where capacity sits and how much of it there is (open, keep, shrink). What happens inside a branch (staffing, service quality, operations) is out of scope. Ratings enter only as *attractiveness*, i.e. how much demand a branch's capacity pulls in, never as something we tell leadership to fix.
- [ ] **OB5. ROIC is a gate, built from stated assumptions.** Services delivered is what we grow, and return on capital decides whether a site is worth it. GROW and PROTECT require clearing the gate.
  ```
  estimated contribution = catchment demand × capture share × visit frequency × margin per visit − fixed site cost
  implied ROIC          = estimated contribution / estimated invested capital
  ```
  - [ ] Catchment demand and capture share come from the model (OB3 / Huff). The rest (visit frequency, margin per visit, fixed site cost, invested capital) are **assumptions**. Each one is either sourced (filings, industry benchmarks, rent data) or explicitly marked **open**. *Which values we can actually find is still open.*
  - [ ] The hurdle is tiered (e.g. below hurdle / acceptable / strong), and the tiers are what the labels key off. We set levels; we don't predict exact returns.
  - [ ] Assumptions are visible next to every ROIC figure. A label that clears the gate only under optimistic assumptions is flagged as such.

*To improve:*

- OB1: labels come from a weighted composite (lounges) and rule tests (areas). Nothing measures demand served by capacity.
- OB2: lounges have no capacity at all. The 200k-women demand anchor ("one lounge can't absorb more", scorecard.py:28-31) is an implicit equal-capacity cap that is never named as one.
- OB3: demand per cell exists, but catchments are all-or-nothing and capacity is never spread over cells. The raw material already exists: `est_customers` (computed, unscored) and cell_isochrones.geojson (fetched, unused).
- OB4: rating is scored as a health signal at half weight, and a cached explanation tells the COO "Improving its rating is the lever to watch" (mirdif-35). That's outside our scope.
- OB5: there's no contribution or ROIC logic and no assumptions anywhere ("No money in the model", limitations §1), and the explanation prompt forbids money.


### Data: sourced, thorough, and detailed enough for the model

- [ ] **DA1. Every input is sourced.** Each model input traces to a named public source, a fetch script and a snapshot date. No hand-typed numbers without a citation.
- [ ] **DA2. Coverage is complete or its gaps are quantified.**
  - [x] Branches: our list is checked against the official Bedashing site. Any branch that's missing, closed or duplicated is accounted for.
  - [ ] Competitors: coverage is checked per emirate or area, so gaps from query limits or category filters are known, not assumed away.
  - [x] Context layers (population, affluence, rent): the share of cells with real vs. imputed or missing values is reported.
- [ ] **DA3. Resolution matches the model.** Each dataset is at least as fine as the spatial unit it feeds. Where coarser data is spread or assigned onto cells (e.g. area-level rent → cells), the method and its error are stated.
- [ ] **DA4. Sufficient for the questions.** For each of Q1–Q4 we can name the signals it needs and the dataset that supplies each one. A question answered with no data behind it, or only by a proxy of a proxy, gets flagged.
- [ ] **DA5. Quality checks run.** Deduplication, points that fall on UAE land, category filtering and outlier review are all done, and tests guard against regressions.
- [ ] **DA6. Missing ≠ zero.** Missing values are explicit, imputation is flagged, and both flow through to per-entity confidence (E4).
- [ ] **DA7. Known biases are named:** Google-review skew (tourists, incentivised reviews), OSM/Places coverage gaps, listing-rent vs. actual-rent bias, and population-raster age.
- [x] **DA8. Freshness is consistent.** Snapshot dates are close enough to be compared, and any big gap is stated.
- [x] **DA9. One current dataset version.** The model and app read a single data version (v3 plus fresh sources). Old seed data isn't mixed in.
- [ ] **DA10. Every dataset earns its place.** Each dataset feeds a model input or a displayed fact. Unused data gets dropped or explained.

*To improve:*

- DA1: the DLD rents were downloaded by hand with no script, lounges.json is a browser snapshot, and search_recall 0.66 and the 0.25–4 clip (market.py:121) have no committed source.
- DA2-competitors: recall isn't tracked per emirate. The correction rests on a single Al Barsha tile, and cells under 2k women outside catchments were never searched.
- DA3: the rent area→cell assignment (102 point-inside, 139 nearest within 2.5 km) has no error estimate.
- DA4: there's no Q→signal→dataset table, and capture is a proxy of a proxy (reviews → customers → share).
- DA5: there's no on-land check (20 candidates sit outside every cell), and outlier review is informal.
- DA6: a missing rent becomes a neutral 1 (an imputation), and a missing review_count becomes 0 (6.7% of salons). AreaDecision has no confidence field.
- DA7: tourist review skew and the modelled, aging nature of the WorldPop raster aren't named.
- DA10: cell_isochrones.geojson (2,430 polygons) is never read by src/.


### Modeling: simple, explainable, answers the questions, holds up against standard methods

- [ ] **MO1. Simple.** We use the fewest inputs and rules that answer Q1–Q4. Every input earns its place: we know what removing it would change, and if the answer is "nothing", it goes.
- [x] **MO2. Explainable by construction.** The score is transparent (rules or additive weights), so per-entity driver contributions (E3) fall out of the model rather than being reverse-engineered afterwards.
- [x] **MO3. Answers the questions.** Each of Q1–Q4 maps to a specific model output field. No question is answered only by the map.
- [ ] **MO4. Benchmarked against standard retail location methods.** For each one we can say what it does, what our model does instead, and how we've accounted for the gap (a limitation, a proxy, or a deliberate simplification):
  - [ ] **Huff gravity model:** patronage probability ∝ attractiveness / distance^λ, shared across competing stores. *Do we cover it?* Distance decay (isochrones), attractiveness (rating/reviews), competitive share. *Gap to account for:* no calibrated λ, no probabilistic split of demand between stores, and hard catchment edges instead of decay.
  - [ ] **Thiessen / Voronoi / nearest-facility trade areas:** each customer goes to the nearest store. Do our catchments and overlaps behave better than this baseline, and do we know where they differ?
  - [ ] **Ring / drive-time analysis:** probably our core method. The mode, minutes and choice of isochrone provider are justified.
  - [ ] **Index of Retail Saturation (IRS):** demand × spend ÷ supply. How our saturation measure relates to it, and what we use as stand-ins for spend and supply capacity.
  - [ ] **Multi-criteria suitability / weighted overlay (MCDA, AHP):** likely what our whitespace model really is. Weights are justified the way MCDA requires (stated, sensitivity-tested), not just picked.
  - [ ] **Location-allocation / maximal coverage (MCLP):** picks the *set* of new sites that maximises coverage. We score cells one by one, so two adjacent GROW cells could cannibalise each other. Stated, or handled.
  - [ ] **Analog / sales-regression models:** these need revenue we don't have. Stated as the main reason our health score is a proxy.
- [ ] **MO5. Validated against reality.** The latest run of [`SANITY_CHECKS.md`](SANITY_CHECKS.md) (back-tests BT1–BT5, sanity checks SC1–SC6) has no unexplained failure, and each expected outcome was written down before the check ran.
- [ ] **MO6. Sensitivity is known** (see 1.7). We report which labels flip under reasonable changes to weights and thresholds. Labels that sit near a boundary are presented as borderline, not as confident calls.
- [ ] **MO7. Not tuned to taste.** Weights and thresholds weren't adjusted until the label mix "looked right". Where we did tune them, we say so and give the target.
- [ ] **MO8. Branch and whitespace models are consistent** (see B1). They use the same catchment, competitor definition and demand measure, so a branch's cell scored by the whitespace model gives an answer that fits with its branch label.
- [ ] **MO9. Parameters live in one place.** Every weight, threshold and radius lives in config with its rationale. No magic numbers scattered through the code.
- [x] **MO10. Failure modes are named with examples,** feeding E4: where the model is known to be wrong or blind, with real cells or branches as illustrations.
- [ ] **MO11. Clustering is modeled, not just penalised.** Salons bunch together for good reasons: malls and high streets concentrate footfall, customers like to compare, and logistics are easier. That's agglomeration, which Huff's attractiveness term and the "competing destinations" extension (Fotheringham) capture. The model treats a cluster as something that pulls in demand up to the point where demand per unit of supply runs out, and it doesn't assume that empty areas away from other salons are automatically better. Validated by BT5.

*To improve:*

- MO1: the affluence layer "changes no call" (README:49-53) but is kept anyway.
- MO4:
  - Huff isn't implemented, and capture has no distance term.
  - Catchments are never compared against a Voronoi baseline.
  - Driving as the ring mode is never argued.
  - Reviews per 1k women is never linked to IRS, and it has no spend term.
  - The weighted overlay is never named as MCDA, and only the rating weight was ever tested.
  - GROW areas are scored independently, so cannibalisation between them is unstated (MCLP).
  - Analog and regression methods aren't named as the reason the health score is a proxy.
- MO5: no sanity check runs as a repeatable script yet. Pass-1 findings live in SANITY_CHECKS.md (BT2, BT3, SC1). The headline finding: scoring each lounge's 15-min catchment with the growth rule gives 22 WATCH ("big but saturated", 88–629 premium reviews per 1k), 2 GROW (al-dhafra, al-falah) and 0 SKIP. The saturation line of 50 was set below every working lounge (decisions.ipynb §7), so the growth model calls our own lounges saturated, which contradicts PROTECT for al-ain.
- MO6: growth areas get no flips and no confidence. There's no weight or threshold sensitivity.
- MO7: estimated customers was rejected partly because of the outcome it produced (limitations §2).
- MO8: the two models differ on demand (catchment vs. OSM-name pieces) and on competition (capture vs. reviews per 1k), and the back-test shows the inconsistency.
- MO11: saturation (premium reviews per 1k women) is a pure penalty in the growth rule, so GROW tends to favour areas with no salons at all (all 4 GROWs are in thin Sharjah-area markets). Agglomeration is never considered.
- MO9: constants are scattered: THIN_MARKET and NOT_SCORED (lounges.py:23-24), the clip (market.py:121), RADIUS_KM and MIN_CONTRACTS (build_affluence.py:44-45), GROWTH_MIN_WOMEN and CIRCLE_M (fetch_salons.py:53,56), MIN_ADULTS (build_cells.py:32).


---

## Traceability: brief → rubric

| Brief section | Requirement | Rubric items |
|---|---|---|
| Context | Protect / hold / shrink | Q1 |
| Context | Where to open | Q2 |
| Context | Self-overlap | Q3 |
| Context | Strength vs. local competition | Q4 |
| Context | Visual, interactive exploration | Q5 |
| Assignment §1 | Branch locations, detail | L1, Q1.8, Q5.2 |
| Assignment §2 | Catchments, same-set overlap | L2, Q3, C1, C7 |
| Assignment §3 | Competitors, density/saturation | L3, Q4.3–4.5, C5, C6 |
| Assignment §4 | Health indicators, comparison method | L4, Q4.1–4.2, 4.6–4.7 |
| Assignment §5 | Branch model, whitespace model | L5, Q1, Q2, B4 |
| Inputs | Branches, ratings, competitors, travel time | S1–S4 (+S5–S9) |
| Expected outcome §1 | Working product | P1–P3 |
| Expected outcome §2 | Technical README | R1–R4 |
| Expected outcome §3 | Short demo | M1–M3 |
| Min. req. A | Business framing | A1–A6 |
| Min. req. B | Recommendation logic | B1–B6 |
| Min. req. C | Geographic reasoning | C1–C9 |
| Min. req. D | AI-relevant design | D1–D8 |
| Min. req. E | Explainability | E1–E5 |
| Constraints | Simplify with reasons, static OK, no polish | X1–X3 |
| Submission format | Repo, README, demo; fallback for secrets | U1–U3, K1–K3 |
| "What we care about" | Framing, research, structure, stack, trade-offs, AI use, delivery | J1–J7 |
| Final note | First / simplify / abstract / trust / automate / explain / ship | H1–H7 |
| *(ours)* | Business focus, ROIC gate, clustering | A7, E6, OB5, MO11 |
| *(ours)* | User stories, back-tests, sanity checks | [`SANITY_CHECKS.md`](SANITY_CHECKS.md) via MO5 |
