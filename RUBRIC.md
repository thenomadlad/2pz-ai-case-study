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
| 2 | 2026-10-10 | 69/80 | 30/40 | 5/26 | **NO-GO**: 11 `[brief]` open (2.5, 4.4, L3, A3, B1, B3, C3, C6, E4, P1, J7); sanity run 1 has unexplained fails | Every non-model gap is closed: docs, UI, explanations (what / so what / now what, enforced) and the walkthrough. What's left is the model: capacity, served demand and ROIC (OB1–OB5), the growth rule (WORKER_CAP bug, a saturation penalty against BT5's clustering evidence) and the airport-in-comparison bug. |


---

## Part 1: The five business questions

These are the product's reason to exist. Part 2 (layers), Part 3 (functional requirements) and Part 4 (data sourcing) all serve these.

### Q1. Which existing branches should we protect, hold, or shrink?

- [x] `[brief]` **1.1 Every branch gets a label.** No branch in the network is missing one. The label set (PROTECT / HOLD / SHRINK, or our own) is defined in one place.
- [x] `[ours]` **1.2 Labels mean an action.** Each label is defined as what leadership should *do*, e.g. "SHRINK = reduce footprint/staff or consolidate into X". A score band alone isn't a definition.
- [x] `[ours]` **1.3 The inputs combine all four lenses:** branch health (Q4), local competition (Q4), self-overlap (Q3) and catchment demand (Layer 2).
- [ ] `[ours]` **1.4 Overlap affects labels only through cannibalization (3.6).** Overlap on its own is never a penalty. A branch moves toward SHRINK only when its capacity exceeds the demand it can reach once shared with our other branches. Overlap that's drawn on the map but has no defined effect on labels fails this item.
- [ ] `[ours]` **1.5 Thresholds are justified.** Every cut-off and weight has a written reason: data-driven, a business rule, or an explicitly stated judgement call.
- [x] `[ours]` **1.6 The distribution makes sense.** The label counts are reported. If one label dominates, there's an explanation, and the model isn't simply defaulting to HOLD.
- [ ] `[ours]` **1.7 Stability is checked.** We know which branches flip labels under reasonable changes to weights or thresholds, and borderline cases are flagged as such.
- [x] `[brief]` **1.8 Branch-level drill-down.** From any branch you can see its label, the drivers behind it, its raw inputs and its caveats (see E1–E4).

*To improve:*

- 1.4 *(model)*: SHRINK is still driven by raw `shared_share` overlap and takes no account of capacity. Blocked on OB3.
- 1.5: the equal 1/1/1 weights and the 0.65/0.35 lines get only a one-line rationale and are never tested against alternatives.
- 1.7 *(model)*: sensitivity covers only the 81 combinations of assumption levels, and weights and thresholds are never varied. The new distance-to-line counterfactual helps but doesn't replace this.
- New *(model)*: the NOT SCORED airport lounge still counts as a sibling (shahama's biggest overlap: 55,620 of 65,769 women) and as a premium substitute for 6 Abu Dhabi lounges. Removing it entirely flips shahama from SHRINK to HOLD (0.318 → 0.383), and the SHRINK action "consolidate into the sibling that shares most" points shahama at the airport. This is disclosed in the README and walkthrough, but not fixed.

### Q2. Where should we consider opening new branches?

- [x] `[brief]` **2.1 The candidate universe is defined.** Areas, grid cells, hexes or districts, with a stated reason for the unit and its resolution.
- [x] `[brief]` **2.2 Every candidate gets a label** (GROW / WATCH / SKIP or our own), and each label means an action.
- [ ] `[ours]` **2.3 Demand side:** a population or affluence proxy, plus a target-customer fit signal.
- [x] `[brief]` **2.4 Supply side:** competitor density or saturation within the candidate's catchment.
- [ ] `[brief]` **2.5 Our own coverage:** distance or travel time to our nearest branch. Whitespace means *unserved demand* (OB3), not "outside our catchments". An under-served area inside our footprint can still be GROW, and an area outside it can be SKIP if competitors already serve it.
- [x] `[ours]` **2.6 SKIP actually happens.** The model rules areas out with a stated reason. A model that only says GROW or WATCH is hedging.
- [x] `[ours]` **2.7 WATCH has a meaning.** It says what would move an area to GROW or SKIP, e.g. "rent data missing" or "demand is OK but saturation is borderline".
- [x] `[ours]` **2.8 Ranking.** Within GROW, candidates are ordered so leadership has a top N, not just a set.
- [ ] `[ours]` **2.9 Geographic realism.** Candidates are reachable, inhabited places. Desert, sea, industrial zones and airports are not proposed unless that's intended and justified.

*To improve:*

- 2.3 *(model/data)*: affluence is still Dubai-only, and there's no target-customer signal elsewhere.
- 2.5 *(model)*: areas are still only cells no lounge reaches, so under-served demand inside the footprint can't be GROW.
- 2.9 *(model)*: this is a bug. The small-and-unsaturated WATCH branch (growth.py:62-64) never applies WORKER_CAP, so 7 industrial, military or free-zone areas come out WATCH (BT4, SC3).

### Q3. Where are we overlapping with ourselves?

- [x] `[brief]` **3.1 Overlap is measured,** as catchment intersection area, shared population, or travel-time overlap. "Two pins are close" isn't a measurement.
- [x] `[ours]` **3.2 Pairwise view.** You can see which branch pairs overlap and by how much.
- [x] `[brief]` **3.3 Same competitive set.** Overlap is only counted between branches that compete for the same customer (same format, tier or service mix), as the brief asks. Any simplification is stated.
- [x] `[brief]` **3.4 It's visible on the map** as overlapping catchments or highlighted pairs.
- [ ] `[ours]` **3.5 It feeds decisions** into Q1 (SHRINK or consolidate when capacity in the shared zone is excess) and Q2 (a new site's demand is counted net of the capacity already reaching it).
- [ ] `[ours]` **3.6 Cannibalization is defined, not assumed.** Overlap counts as cannibalization only when demand in the shared zone is less than the combined capacity reaching it (OB3). Overlap where demand is high is legitimate density, and it also keeps competitors out. The definition lives in one place in the code and docs, and it's the only route by which overlap changes a label.

*To improve:*

- 3.5, 3.6 *(model)*: overlap is never compared with demand or capacity. Q2 drops reached cells instead of netting out capacity. Blocked on OB2/OB3.

### Q4. How strong or weak is each branch relative to local competition?

- [x] `[brief]` **4.1 Branch health signals:** ratings, review volume, review recency or trend, or other performance proxies. Each one names its source and date.
- [x] `[brief]` **4.2 Relative, not absolute.** Each branch is compared with the competitors in *its* catchment (e.g. rating percentile among local salons), not only with a network-wide average.
- [x] `[brief]` **4.3 Competitive density indicators:** a count and/or per-capita measure of competitors in each catchment.
- [ ] `[brief]` **4.4 Saturation indicator:** a supply-vs-demand measure such as salons per 10k population or per unit of spend.
- [x] `[ours]` **4.5 Competitor definition.** What counts as a competitor (category, tier, minimum review count) is written down, and noise like barbers or nail-only shops is handled deliberately.
- [ ] `[ours]` **4.6 Small-sample handling.** A 5.0 rating from 3 reviews is not treated as equal to 4.6 from 900. We use shrinkage, a minimum-n rule or a flag.
- [x] `[brief]` **4.7 A comparison method.** There's a side-by-side view, a ranking or a scorecard across branches on common axes.

*To improve:*

- 4.4 *(model)*: lounges have no per-capita saturation figure. It's cheap: reuse the areas' premium reviews per 1k women over the catchment.
- 4.6: the substitutes' median rating has no minimum-n rule and no shrinkage.

### Q5. How can decision-makers explore these answers visually and interactively?

- [x] `[brief]` **5.1 Map-first overview:** branches, competitors, catchments and opportunity areas on one map, with toggleable layers.
- [x] `[brief]` **5.2 A drill-down page** for each branch and each opportunity area.
- [x] `[ours]` **5.3 Filters and sorting** by label, score, area or emirate.
- [x] `[ours]` **5.4 Legends and labels** let a non-technical exec read the map without being told what the colors mean.
- [ ] `[ours]` **5.5 What-if or scenario control** (e.g. adjust weights or thresholds and see labels change). Nice to have, but it directly supports "defensible".
- [x] `[ours]` **5.6 The AI layer is reachable from the UI** (see D). It isn't hidden in a notebook.
- [x] `[ours]` **5.7 It works on a reviewer's screen.** Reasonable load time, and nothing breaks at a laptop window size.

*To improve:*

- 5.5 *(model)*: the what-if can't change weights or thresholds. That needs the model to accept weights as an input.

---

## Part 2: Required layers (minimum explorable content)

The brief lists these as the minimum content of the product. Most of the substance is covered in Part 1, so this part checks that each layer is present and explorable.

- [x] `[brief]` **L1. Current branch network:** branch locations ✔ branch-level detail (address, rating, reviews, services or tier, label) ✔ → see Q1.8, Q5.2
- [x] `[brief]` **L2. Catchment / coverage:** catchment areas or service radii ✔ overlap between branches in the same competitive set ✔ → see Q3
- [ ] `[brief]` **L3. Competition:** nearby competitors ✔ density or saturation indicators ✔ → see Q4.3–4.5
- [x] `[brief]` **L4. Performance / health:** quality or performance indicators ✔ a method for comparing branches ✔ → see Q4.1, 4.2, 4.6, 4.7
- [x] `[brief]` **L5. Decision layer:** model for existing branches ✔ model for whitespace ✔ → see Q1, Q2

*To improve:*

- L3 *(model/data)*: lounges have no saturation figure (see 4.4), and non-premium salons are never mapped.

---

## Part 3: Minimum functional requirements (A–E)

### A. Business framing

- [x] `[brief]` **A1. Decision-maker named:** who they are (e.g. Head of Network / portfolio team / CEO) and what they care about.
- [x] `[brief]` **A2. Decisions enumerated:** the specific decisions, each tied to a label set, e.g. "approve lease renewal → PROTECT/HOLD/SHRINK".
- [ ] `[brief]` **A3. Metrics that matter:** the north-star metric (services delivered, OB1) and the proxies standing in for it are named. Each signal is listed with *why* it matters for the decision, not just *that* we computed it.
- [x] `[brief]` **A4. How the system supports the decision:** the flow from question to screen to evidence to action is stated.
- [x] `[ours]` **A5. Out of scope** is stated: actual P&L (we only model contribution from assumptions, see OB5), in-branch staffing, quality management and operations, and anything else we deliberately don't model, with the reason. Our job ends once capacity is allocated to sites (OB4).
- [x] `[ours]` **A6. Framing shows up up front:** in the README and the demo opening, not only in a design doc.
- [x] `[ours]` **A7. The first page leads with the business.** The overview opens on the COO's question and the headline answer (e.g. "N lounges to protect, M under pressure, top 3 openings, and what's at stake") before any map layer or score. Someone who reads only the first screen should know what to do next.

*To improve:*

- A3 *(model)*: the north star and its proxy (`est_customers`) are now named, but the proxy drives no label, and the signals aren't tied to services delivered.

### B. Recommendation logic

The brief says it must be **coherent, explainable, defensible**. It does not have to be mathematically perfect.

- [ ] `[brief]` **B1. Coherent:** the same inputs give the same outputs, labels are mutually exclusive, there are no contradictions (e.g. the best-rated, least-overlapped branch marked SHRINK without a stated reason), and the branch and whitespace models share their definitions (same catchment, same competitor set).
- [x] `[brief]` **B2. Explainable:** the logic fits on one page (rules, score formula, decision tree) and a non-technical reader could follow it.
- [ ] `[brief]` **B3. Defensible:** every weight and threshold has a rationale (see 1.5), the method choice is justified against at least one alternative we considered, and we've sanity-checked the output against local knowledge or spot checks.
- [x] `[brief]` **B4. Covers both populations:** existing branches *and* opportunity areas.
- [x] `[ours]` **B5. Tested:** unit tests pin the classification rules, and a regression check catches unintended label changes.
- [x] `[ours]` **B6. Reproducible:** one command rebuilds the scores and labels from the sourced data.

*To improve:*

- B1 *(model)*: the lounge and growth models use different units, and the growth line sits below every lounge market (BT3 shows no agreement). The airport bug is in 1.4.
- B3: the equal weights are still never argued (see 1.5).

### C. Geographic reasoning

The brief asks us to use geography *meaningfully*. Each item below should both exist and affect a recommendation.

- [x] `[brief]` **C1. Catchments,** preferably travel-time based (isochrones). Radii are acceptable with a stated reason.
- [x] `[brief]` **C2. Proximity:** distance or time to competitors and to our own branches.
- [ ] `[brief]` **C3. Overlap:** see Q3.
- [x] `[brief]` **C4. Coverage gaps:** populated areas outside our catchments are identified, and that feeds Q2.
- [x] `[brief]` **C5. Competitor density:** see Q4.3.
- [ ] `[brief]` **C6. Market saturation:** see Q4.4.
- [x] `[brief]` **C7. Travel-time logic,** with the drive-time mode and minute threshold stated and justified for UAE car-centric travel.
- [x] `[ours]` **C8. Spatial unit and CRS are sound:** areas are computed in a metric projection, not raw degrees, and the cell size is justified.
- [x] `[brief]` **C9. Geography changes outcomes.** At least one example shows a label that is *because of* a spatial factor (overlap, gap, saturation).

*To improve:*

- C3 *(model)*: overlap is now on the map, but it's never weighed against demand or capacity (see 3.6).
- C6 *(model)*: lounge catchments have no supply-vs-demand figure (see 4.4).

### D. AI-relevant design

The brief says the AI layer must be practical, not gimmicky.

- [x] `[brief]` **D1. At least one meaningful AI layer.** Possible kinds: NL interaction, AI-assisted explanation, grounded summaries, a tool-using analyst, prompt/tool/retrieval design, or an agentic flow. Name the one we chose.
- [x] `[brief]` **D2. Grounded:** AI output is generated from our computed data, so every number it states can be traced to a field. No invented facts.
- [x] `[ours]` **D3. Groundedness is verified:** there's an automated check or a documented review showing outputs match the data.
- [x] `[brief]` **D4. Practical value:** the layer saves the decision-maker time or adds insight the raw table doesn't. We can say what a user would do without it.
- [x] `[ours]` **D5. The AI explains the model, it doesn't make the decisions.** If labels come from deterministic logic and the AI only narrates them, we say so as a trust choice.
- [x] `[ours]` **D6. Prompt and design are visible:** the prompt or tool schema is in the repo, along with why we designed it that way.
- [x] `[brief]` **D7. Failure modes are handled:** no API key, rate limits, stale cache. An offline or cached mode keeps the product working (see Part 5).
- [x] `[brief]` **D8. Responsible use:** limitations of the AI layer are stated (hallucination risk, what it can't see), and so is how AI tools were used to *build* the solution.

*To improve:*

- D3 (passes): a cache hit at runtime is still served without re-verifying. The committed-cache test guards the cache instead. Acceptable.
- D2/E5 (passes, known `verify()` gaps): number words aren't grounded, only the headline's first label word is checked, and over-vs-short wording isn't checked. A pass-2 overclaim in al-dhahir's so-what had to be fixed by hand.

### E. Explainability

From the reviewer's seat, each question below should be answerable **for any single branch or area, in the product, in under a minute**.

- [x] `[brief]` **E1. "Why did this branch get this recommendation?"** Per-branch rationale: which rule or threshold fired, and the input values that triggered it.
- [x] `[brief]` **E2. "Why is this area attractive or unattractive?"** Per-area rationale, both its demand and its supply side, including why it's *not* GROW when it's WATCH or SKIP.
- [x] `[brief]` **E3. "Which inputs most influenced the outcome?"** Per-entity input attribution: contribution breakdown, rank of drivers, or a counterfactual ("would be GROW if saturation < X"). Saying which rule fired doesn't answer this. We need magnitudes or ordering.
- [ ] `[brief]` **E4. "Where should we trust the model, and where should we be careful?"**
  - [x] Global: a limitations doc covering data gaps, proxies, biases and staleness.
  - [ ] Per entity: confidence or caveat flags on the specific recommendation (missing data, low review count, imputed values, borderline score).
  - [x] Known failure cases are named, with examples.
- [x] `[ours]` **E5. Consistency:** the explanation and the label never disagree, and an automated test enforces it.
- [ ] `[ours]` **E6. What / so what / now what.** Every recommendation, whether in the generated text, the UI or the demo, answers all three:
  - **What:** the label and the two or three facts behind it, with numbers.
  - **So what:** the business consequence in the COO's terms, i.e. services and demand at stake, the competitive position, and whether it clears the ROIC gate (OB5).
  - **Now what:** the action leadership should take, and what would change the call.

  "GROW because the demand score is 0.8" fails this item. A factor-level explanation alone is a *what* without a *so what*. The prompt for generated text has to require all three parts, and a spot check of generated outputs confirms it does.

*To improve:*

- E4-entity: areas still have no confidence grade, and nothing flags an area near the size line (al-awir is 78 women over, kalba 3,464). Small-n ratings aren't flagged.
- E6 *(model)*: what / so what / now what now holds for all 65 explanations, but no so-what can address the ROIC gate (OB5).

---

## Part 4: Data sourcing

The brief says to source inputs from public sources and lists some combination of these.

- [x] `[brief]` **S1. Branch location data,** with its source.
- [x] `[brief]` **S2. Ratings / review signals,** with source and pull date.
- [x] `[brief]` **S3. Competitor data,** with source, query definition and coverage.
- [x] `[brief]` **S4. Precomputed travel-time / catchment data,** with the provider and parameters.
- [x] `[ours]` **S5. Further context data** (population, affluence, rent, etc.), each with a stated reason for inclusion.
- [x] `[ours]` **S6. Data inventory:** source, date, licence or ToS, row counts and known gaps for every dataset.
- [x] `[ours]` **S7. Provenance in the product:** a reviewer can tell where a number came from.
- [x] `[ours]` **S8. Proxy honesty:** wherever we use a proxy (e.g. reviews standing in for revenue), the gap between proxy and truth is stated.
- [x] `[ours]` **S9. Fetch scripts are reproducible**, or the committed snapshots are explained if re-fetching needs paid keys.

*To improve:*

- (none open)

---

## Part 5: Deliverables and submission

### Working product

- [ ] `[brief]` **P1. Usable end to end:** a reviewer can go from overview to a recommendation to its explanation without help.
- [x] `[brief]` **P2. The format is justified:** why a web app, notebook, agent or whatever we picked suits this decision-maker.
- [x] `[brief]` **P3. Easy to run:** one or two commands, or a hosted link.

### Technical README

- [x] `[brief]` **R1. Setup and run instructions** that work on a clean machine, verified.
- [x] `[brief]` **R2. Written for time-constrained reviewers:** a TL;DR at the top, the live link first, and a "what to look at in 5 minutes" path.
- [x] `[brief]` **R3. Architecture and tech-stack rationale:** why these tools.
- [x] `[ours]` **R4. Pointers** to the framing (A), logic (B), limitations (E4) and data inventory (S6).

### Demo

- [x] `[brief]` **M1. One of:** a 5–10 minute recorded walkthrough, **or** a live hosted version plus a short written walkthrough.
- [x] `[ours]` **M2. It covers** framing → the map → a branch decision with its explanation → an opportunity with its explanation → the AI layer → limitations.
- [x] `[brief]` **M3. If recorded, it fits in 5–10 minutes.**

### Secrets and paid APIs

- [x] `[brief]` **K1. A fallback mode** exists for anything needing secrets or paid APIs, and the product works without keys.
- [x] `[brief]` **K2. Otherwise, screenshots or a recording** show the paid path working.
- [x] `[ours]` **K3. No secrets** are committed to the repo.

### Submission bundle

- [x] `[brief]` **U1.** Link to the source repository
- [x] `[brief]` **U2.** README with run instructions
- [x] `[brief]` **U3.** Demo video or live link

*To improve:*

- P1: the live app redeploys from `main` and hasn't been clicked through since these changes; recheck it after the push. A local visual check passed on 2026-10-10: the overview at 1280 px and the shahama page at 800 px, with no overflow and no exceptions.

---

## Part 6: Constraints and how we're judged

### Constraints we're allowed to lean on, as long as we use them deliberately

- [x] `[brief]` **X1. Simplifications are explained.** Every simplification ("you may simplify parts of the problem if you explain why") is listed with its reason and its cost.
- [x] `[brief]` **X2. Static files instead of a backend** is a stated choice, if we made it.
- [x] `[brief]` **X3. No time spent on irrelevant production polish.** Anything production-grade we built has to materially improve the case.

### Evaluation lenses

The brief says *"this is not a coding test"*. Each lens needs a visible artifact.

- [x] `[brief]` **J1. Problem framing:** see A.
- [x] `[brief]` **J2. Research:** how we found and vetted the data and the domain assumptions (see S6, design docs).
- [x] `[brief]` **J3. Solution structure:** pipeline stages are clear (sourcing → features → model → explain → UI).
- [x] `[brief]` **J4. Tech-stack decision:** see R3.
- [x] `[brief]` **J5. Trade-offs:** a written list of what we chose, what we gave up and why.
- [x] `[brief]` **J6. Responsible and effective AI use:** see D8, covering both AI in the product and AI in the build.
- [ ] `[brief]` **J7. Usable delivery:** see P1–P3.

### The closing "hardest part" questions

Each should have a one-paragraph answer somewhere a reviewer will find it, such as the README or a decisions doc.

- [x] `[brief]` **H1.** What problem did we solve first, and why?
- [x] `[brief]` **H2.** What did we simplify?
- [x] `[brief]` **H3.** How did we abstract (the spatial unit, scores, labels)?
- [x] `[brief]` **H4.** What did we trust, and what didn't we?
- [x] `[brief]` **H5.** What did we automate?
- [x] `[brief]` **H6.** What did we explain?
- [x] `[brief]` **H7.** What did we ship, and what didn't we?

*To improve:*

- J7: follows P1.
- Hygiene: untracked files at the repo root (`ai-associate-case-study.docx`, `transactions-2026-10-10.csv`, `.ropeproject/`, `.superpowers/`). Keep them out of commits, or gitignore or move them.

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

- OB1–OB3, OB5 *(model)*: unchanged. There's no capacity, no served vs. unserved demand and no ROIC. The README now admits all of this (README:72-77, "No money in the model").
- OB4: in-branch advice is now banned and enforced by `verify()` (0 of 65 hits). Remaining gap *(model)*: rating is still a half-weight health signal in the composite, not an attractiveness term.

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

- DA1 *(model/data)*: the DLD rents were still downloaded by hand with no script, and search_recall 0.66 and the 0.25–4 clip have no committed source.
- DA2-competitors *(model/data)*: recall still isn't tracked per emirate, and the correction still rests on one tile.
- DA3 *(model/data)*: there's no error estimate for the rent area→cell assignment.
- DA4 (a cheap doc fix): there's still no Q1–Q4 → signal → dataset table, and capture is a proxy of a proxy.
- DA5 *(model/data)*: there's no on-land check, and outlier review is informal.
- DA6 *(model)*: a missing review_count becomes 0, and areas have no confidence.
- DA7 (a cheap doc fix): tourist review skew is never named, and WorldPop is never called modelled.
- DA10: cell_isochrones.geojson is listed as an input, but src/ never reads it.
- SC1 *(model/data)*: the Dubai Marina cell sits outside every catchment as a SKIP area with 2,052 women; it's probably a grid or centre-point artefact.

### Modeling: simple, explainable, answers the questions, holds up against standard methods

- [ ] **MO1. Simple.** We use the fewest inputs and rules that answer Q1–Q4. Every input earns its place: we know what removing it would change, and if the answer is "nothing", it goes.
- [x] **MO2. Explainable by construction.** The score is transparent (rules or additive weights), so per-entity driver contributions (E3) fall out of the model rather than being reverse-engineered afterwards.
- [x] **MO3. Answers the questions.** Each of Q1–Q4 maps to a specific model output field. No question is answered only by the map.
- [ ] **MO4. Benchmarked against standard retail location methods.** For each one we can say what it does, what our model does instead, and how we've accounted for the gap (a limitation, a proxy, or a deliberate simplification):
  - [ ] **Huff gravity model:** patronage probability ∝ attractiveness / distance^λ, shared across competing stores. *Do we cover it?* Distance decay (isochrones), attractiveness (rating/reviews), competitive share. *Gap to account for:* no calibrated λ, no probabilistic split of demand between stores, and hard catchment edges instead of decay.
  - [ ] **Thiessen / Voronoi / nearest-facility trade areas:** each customer goes to the nearest store. Do our catchments and overlaps behave better than this baseline, and do we know where they differ?
  - [x] **Ring / drive-time analysis:** probably our core method. The mode, minutes and choice of isochrone provider are justified.
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

- MO1 *(model)*: the affluence layer "changes no call" but is kept.
- MO4: Huff is named as given up, with a reason. Voronoi, IRS, MCDA, MCLP and analog are never named; one paragraph in limitations would fix that cheaply.
- MO5: NO-GO. See SANITY_CHECKS run 1: BT2, BT3, BT4, SC3 and BT5 fail.
- MO6, MO7 *(model)*: there's no sensitivity to weights or thresholds, and areas have no confidence.
- MO8 *(model)*: BT3 shows no relationship between a lounge's label and the growth label of its own site.
- MO9 *(model)*: constants are still scattered (lounges.py:23-24, market.py:121, growth.py:17-21, scripts).
- MO11 *(model)*: BT5 says clustering helps a little and never hurts. Isolated premium salons have a median of 126 reviews, against about 220 for those with 3+ premium neighbours within 1.5 km. But saturation is a pure penalty: 0 of 123 GROW cells sit next to a premium cluster.
- New *(model)* (SC4 bugs):
  - The THIN_MARKET=10 cliff: three 5-review salons lift al-dhafra from 0.485 to 0.628, close to PROTECT.
  - The median-based premium test isn't monotone: adding a popular mid-market salon lowers measured saturation in 32 areas.

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
