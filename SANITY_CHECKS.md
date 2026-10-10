# Sanity Checks

[`RUBRIC.md`](RUBRIC.md) asks whether the solution has what it needs. This file asks whether the answers are **believable**: whether a COO can actually use them, whether the model rediscovers what we already know, and whether it fails in the places it should. The rubric is the go/no-go gate, and a clean run of this file is one of its conditions (MO5).

## When to run

- **On every rubric pass.**
- **After any change** to `src/model/`, `src/features/`, `src/market.py`, `data/seed/` or `data/scenarios/baseline.yaml`, run at least the back-tests and SC2–SC4.
- **Before a demo or submission,** run everything.

Record each run in the log at the bottom.

## Rules

1. **Write the expected outcome before running.** Every check below states one. If the expectation changes, change it in a commit of its own, with the reason.
2. **Don't tune to pass.** A failing check means one of three things: a model bug, a data bug, or a real finding that needs explaining. Record which. Moving a threshold until the check goes green is tuning to taste (rubric MO7). The 24 lounges are both our calibration set and our validation set, so treat them with suspicion.
3. **A failure is only unexplained until we write it up.** "BT2: al-ain reads saturated because the market filled in after it opened; we accept that" is an explained failure. It counts toward GO, but it still belongs in the limitations doc.

---

## 1. User stories (walk through the app as the COO)

Open the app as the **COO**, who is accountable for lounge operations and return on capital. Try each story. Tick it only if the answer is *findable in the product without help*, *grounded in our data* and *framed in business terms* (rubric E6). A failure points at the rubric items listed, and that's where the To-improve note goes.

#### From the overview

- [ ] **US1. "Where is the pressure in my network?"** At a glance I can see which lounges and areas are under pressure (saturated catchments, cannibalization, SHRINK candidates) and roughly how much is at stake. *Rubric: A7, Q1, Q3, Q4.4, 5.1*
- [x] **US2. "Why was this decision made?"** From the overview, one click on a lounge or area shows its label, the business reason (what / so what / now what), the top drivers with their weight, and caveats. *Rubric: E1–E4, E6, 1.8*
- [ ] **US3. "Who am I up against here?"** I can see the competitors around any lounge: where they are, how many, how they're rated next to us, and whether the catchment is saturated. *Rubric: Q4, L3, C5, C6*
- [ ] **US4. "Where should we open next?"** A ranked shortlist of GROW areas, each showing the unserved demand it captures, its ROIC gate tier, and the reason. *Rubric: Q2, 2.8, OB3, OB5*

#### Drilling in

- [ ] **US5. "Are these two lounges eating each other?"** For an overlapping pair I can see whether it's cannibalization or healthy density, and why. *Rubric: Q3, 3.6*
- [x] **US6. "Why not here?"** For a WATCH or SKIP area, I can see what's holding it back and what would have to change for it to become GROW. *Rubric: 2.6, 2.7, E2*
- [ ] **US7. "Does this one actually pay?"** For any GROW or PROTECT call I can see the contribution and ROIC estimate, the assumptions behind them, and whether the call survives pessimistic assumptions. *Rubric: OB5*
- [x] **US8. "How much should I trust this?"** Every recommendation shows its confidence and what data is missing or proxied. *Rubric: E4, DA6*

#### Asking the AI

- [ ] **US9. Plain-English question.** For example, "Which Dubai lounges are under the most pressure and why?" gets a grounded answer in what / so what / now what form, with numbers that match the screens. *Rubric: D1, D2, D4, E6*
- [ ] **US10. "What if?"** For example, "What if margin per visit is 20% lower?" or "What if we weight competition more?". I can see which labels change. *Rubric: 5.5, MO6, OB5*

**Notes from run 1 (2026-10-10, rubric pass 2).** US2 now passes: one click shows the label, so what / now what, the top drivers with their weights, and caveats. US4 moved from FAIL to PARTIAL.

- US1 *(model/data)*: the question, at-stake figures and overlap map now lead the overview. Lounges still have no saturation figure, and the stake is in women only. The at-stake row mixes units: SHRINK and PROTECT count raw women 15+, GROW counts affluence-weighted addressable women.
- US3 *(model/data)*: there's no catchment saturation, and only premium salons are mapped.
- US4 *(model)*: there's now a ranked GROW list with reasons, but no figure for demand left unserved after existing capacity, and no ROIC tier.
- US5 *(model)*: overlap is visible, but the app never judges cannibalisation against healthy density.
- US7 *(model)*: there's no money in the model.
- US8: passes in run 2. Areas now carry low/medium/high, and lounges show weight flips.
- US9: there's no free-text question box. It's deliberately skipped because live Q&A needs paid API calls on every question, against the no-API-spend rule. Revisit if that rule changes.
- US10 *(model)*: the what-if covers levels, recall and closures; weights and margin can't be changed.

---

## 2. Back-tests (does the model rediscover what we know?)

The 24 operating lounges are our only revealed-preference data: Bedashing picked these sites, and they're still open. That's weak evidence. We only see survivors, we see today's market rather than the one each lounge opened into, and existence isn't the same as success. So these are diagnostics to explain, not targets to tune toward.

- [ ] **BT1. Leave-one-out rediscovery.** *(Needs the OB3 served/unserved model.)* For each lounge X: remove it, rerun, and check whether its old catchment shows up as unserved demand.
  - *Expected:* PROTECT lounges are rediscovered as GROW. SHRINK lounges' demand is mostly absorbed by their siblings, so it doesn't light up. HOLD lounges fall in between.
  - *Why:* this is the cleanest test of the services-delivered logic. It's the one back-test with a natural expected answer for every lounge.
- [ ] **BT2. Same-unit scoring.** Score each lounge's site with exactly the unit the growth model uses for a candidate at that spot. Don't use the lounge's full catchment, and don't use a single cell.
  - *Expected:* no PROTECT lounge comes out SKIP, and any WATCH has a stated reason.
  - *Run 1:* the growth model has no candidate-site unit. The nearest fair approximation is the lounge's own named neighbourhood, with the "not reached" filter dropped. That gives 16 SKIP, 6 WATCH, 2 GROW, and **all 3 PROTECT lounges come out SKIP** (al-ain 5.0k women / 151 premium reviews per 1k, al-taif-mall 2.4k / 896, ras-al-khaimah 4.3k / 140). Part of that is the unit, since neighbourhood pieces are small. The real finding is that 20 of 23 scored lounges sit above the 50-per-1k line. **FAIL, unexplained.**
  - *Run 2:* all 3 PROTECT lounges still come out SKIP, but now on **size** only: al-ain 5.0k women, al-taif-mall 2.4k, ras-al-khaimah 4.3k. On their catchments all three sit under the new 150 line (122 / 113 / 145). **FAIL, explained:** the neighbourhood unit is tiny, and there's still no candidate-site unit (structural, OB3).
  - *Pass 1 (wrong unit, so for reference only):* scored on their 15-min catchments, the lounges come out 22 WATCH ("big but saturated", 88–629 premium reviews per 1k women), 2 GROW (al-dhafra, al-falah) and 0 SKIP. Scored on their own cell, all 24 come out SKIP, which reflects the unit, not the model. The real finding is that the saturation line of 50 sits below every working lounge's market, so the growth model would refuse to enter the markets we operate in successfully.
- [ ] **BT3. Cross-model agreement.** Cross-tabulate each lounge's label against the growth label of its own site (from BT2).
  - *Expected:* PROTECT ↔ GROW, or WATCH for a stated reason other than saturation. A lounge marked SHRINK because of cannibalisation can still sit in a strong market, so any disagreement needs an explanation.
  - *Run 1:* PROTECT→SKIP 3; HOLD→SKIP 7 / WATCH 4 / GROW 2; SHRINK→SKIP 5 / WATCH 2. There's no relationship between the two (rubric B1, MO8). The one sensible case is shahama: SHRINK, in an unsaturated WATCH neighbourhood (34 per 1k), which fits "cannibalised, but the market is fine". **FAIL, unexplained.**
  - *Run 2:* PROTECT→SKIP 3 (on size); HOLD→WATCH 5 / GROW 4 / SKIP 5; SHRINK→SKIP 5 / WATCH 1. The saturation half of the contradiction is gone. The unit half remains, and by construction (p25) 16 of 21 real-market lounges read above 150. **FAIL, explained** (limitations: growth area ≠ catchment).
- [ ] **BT4. Negative controls.** A fixed list of places that should never be recommended.
  - *Expected:* SKIP, with a sensible reason.
  - *Seed list:* jabal-ali-industrial-3, dubai-investments-park, jebel-ali-north-free-zone, new-industrial-ajman, al-ruways-industrial-city, zayed-military-city, plus open desert and airport cells.
  - *Run 1:* all six still come out WATCH. Cause: the small-and-unsaturated WATCH branch (growth.py:62-64) never applies WORKER_CAP. JAFZ North has 89% worker housing and still comes out WATCH. **FAIL, model bug.**
  - *Run 2:* 5 of 6 are now SKIP, all through the non-residential name rule; the worker-cap fix alone caught none at baseline. Dubai Investments Park stays WATCH (4% worker housing). It's mixed-use with residential communities, and limitations §8 accepts it as "revisit, not open". **PARTIAL, explained.**
- [ ] **BT5. Agglomeration: do salons win by clustering?** Retail bunches up: there's a salon floor in every mall, and capturing demand in a busy hub is easier than in an empty area. Test which force actually dominates in the UAE.
  - *Method, part 1:* for every premium salon, relate its success proxy (review volume and rating) to how many other salons sit near it (same building or mall, within 500 m, within 5 min).
  - *Method, part 2:* check the share of our own lounges and of the top-decile competitors that sit in malls or clusters, against the share of GROW areas with no salon nearby.
  - *Expected (hypothesis):* success rises with local density up to some point. If so, saturation can't be a pure penalty (rubric MO11), and the growth model's tilt toward empty areas is a bug, not a feature.
  - *Confound to state:* malls bring footfall and tourists, and tourists leave reviews, so review volume overstates mall salons (DA7).
  - *Run 1:* 1,129 premium competitors were scored; the correlations use the 765 whose surrounding cells were all searched.

    | Neighbours | ρ vs. reviews | ρ vs. rating |
    |---|---|---|
    | Premium salons within 500 m | 0.10 (p = .004) | 0.16 |
    | Premium salons within 1.5 km | 0.12 | 0.16 |

    - Median reviews by premium salons within 1.5 km: 126 with 0–2 neighbours, about 220 with 3–50. The jump is from isolated to "a few", then it plateaus. There's no penalty at any density.
    - Mall addresses don't explain it: the effect holds outside malls.
    - Population partly does: the effect is 0.14–0.16 in the low-population tercile but about 0 in the high one.
    - Our own lounge cells: 19 of 24 have a premium salon within 1.5 km. GROW cells: only 13% (0 of 123 next to a cluster).
    - Known biases: the 20-result search cap undercounts dense spots, and the premium rule selects on reviews.

    **Verdict: the hypothesis is weakly supported.** Clustering doesn't hurt and helps a little, so treating saturation as a pure penalty is wrong-signed for small clusters (rubric MO11). **FAIL against the model.**
  - *Run 2:* the data are unchanged, so the result is identical. Against the model it's still a FAIL, though explained: the 150 line reduced the tilt, but 0 of 128 GROW cells sit next to a premium cluster. The binding constraint is now the 20k size rule plus the unreached-cells-only universe (structural, OB3).

---

## 3. Sanity checks (cheap, directional, run often)

- [ ] **SC1. Spot checks.** Known hot markets (Dubai Marina, JLT, Downtown, Al Barsha, Abu Dhabi Corniche) read as high demand and high competition. Known empty or non-residential areas read as SKIP.
  - *Run 1:* hot cells read as very high competition: Marina 4,126, JLT 1,954, Downtown 1,932, Al Barsha 274, AD Corniche 1,373 premium reviews per 1k. Their demand sits in the 81st–100th percentile. **PARTIAL.**
  - *Run 2:* unchanged.
  - *Anomaly:* the Dubai Marina cell sits outside every 15-min catchment as a SKIP area with 2,052 women (WorldPop: 5,552 adults). Probably a grid or centre-point artefact (data/unit issue).
- [x] **SC2. Label distribution.** Report the counts on every run, and investigate any big swing that the change doesn't explain. *Pass 1:* lounges 3 PROTECT / 13 HOLD / 7 SHRINK / 1 not scored; areas 4 GROW / 37 WATCH / 539 SKIP. *Run 1:* unchanged (the model didn't change). *Run 2:* lounges 3 / 14 / 6 / 1, areas 5 / 35 / 540. Every swing is attributed: shahama SHRINK → HOLD (airport out); al-jerf GROW (150 line); 6 WATCH → SKIP (name rule); 5 SKIP → WATCH (150 line).
- [ ] **SC3. Geographic realism.** No GROW or WATCH falls in an industrial, military, free-zone, desert or airport area unless it has a written justification (rubric 2.9; overlaps with BT4). *Run 1:* 7 such areas are WATCH (the BT4 six plus jabal-ali-industrial-2, which is 90% worker housing). **FAIL, model bug** (same branch as BT4). *Run 2:* 29 areas are SKIP by name, and only Dubai Investments Park remains (documented). **PARTIAL, explained.**
- [ ] **SC4. Monotonicity.** These should always hold:
  - More demand in a cell never lowers its label.
  - Adding a competitor never raises a label.
  - Closing a sibling never pushes a lounge toward SHRINK.
  - A higher margin assumption never fails the ROIC gate where a lower one passed (OB5).

  These are cheap enough to become unit tests.

  *Run 1:* no label broke a rule, so **PARTIAL**, but two latent bugs turned up:
  - **More demand:** +50% women never lowered a label (23 lounges, 576 areas).
  - **Closing a sibling:** never pushed a lounge toward SHRINK, though three composites dipped through the substitutes' median rating.
  - **Adding a competitor:**
    - *THIN_MARKET cliff:* three 5-review "expensive" salons lift al-dhafra from 0.485 to 0.628 and al-falah from 0.481 to 0.624, because capture switches from neutral to its real value.
    - *Median-based premium test:* in 32 areas, adding a popular mid-market salon *lowers* measured saturation (e.g. al-bustan-ajman 63.7 → 0).
  - **Margin / ROIC rule:** not testable yet.

  *Run 2:* **FAIL, unexplained model bug.**
  - The thin-market cliff is gone: one extra salon adds +0.014, against +0.14 before.
  - The median-based premium test is still non-monotone in 32 areas, with no label effect. Deliberately deferred.
  - **New:** adding one unpriced 4.9★ salon (259 reviews) to al-maqta flips it from **SHRINK to HOLD** (0.341 → 0.351). The rating gap is taken over the top-k substitutes, with k from `coverage_k`. The extra salon raises k from 20 to 21 and moves the median from 4.65 to 4.60. The bug was latent; A1 moved al-maqta to 0.01 under the line, which exposed it. Fix: take the median over a fixed set.
- [x] **SC5. Explanation read-through.** Read 5 random cached explanations: 3 lounges and 2 areas. Each must pass what / so what / now what (rubric E6), and nothing in them should tell the COO to fix something inside a branch (OB4). *Pass 1:* fails. Kalba is a bare "what", and mirdif-35 says "Improving its rating is the lever to watch". *Run 1:* **PASS.** The sample was khalifa-city-a, noya-plaza, al-dhafra, madinat-hind-4 and digdaga, and across all 65 there are 0 in-branch hits and no missing so-what or now-what. One overclaim was found and fixed by hand: al-dhahir's "half the market a lounge runs on". *Run 2:* **PASS** on the regenerated cache (64 entries; sample noya-plaza, jumeirah-park, al-ain, al-dhahir, al-bihouth). Some so-whats only restate figures (rubric E6 note).
- [ ] **SC6. Orders of magnitude.** *(Needs OB2/OB5.)* Estimated services per lounge fit within plausible capacity (specialists × hours), and the contribution and ROIC figures land in a believable range for UAE salons. Nothing should claim a 300% ROIC.

---

## Expected outcomes for run 2 (written 2026-10-10, before the fixes)

What the run-2 fixes are expected to do. Each fix uses the current model, with no structural change.

- **A1, the airport leaves the comparisons** (no sibling overlap, no substitute):
  - shahama flips from SHRINK to HOLD (about 0.32 → 0.38).
  - No other lounge changes label.
  - The airport's catchment cells become eligible for growth areas, which come out mostly SKIP or WATCH.
- **A2 and A3, worker-housing cap on the small-area WATCH branch; non-residential names excluded:**
  - The 7 industrial, military and free-zone WATCHes from BT4/SC3 become SKIP.
  - No GROW changes.
- **A4, the thin-market blend:**
  - No lounge label changes.
  - al-dhafra and al-falah composites move by less than 0.1.
- **D1(a), the saturation line recalibrated.** The rule is fixed *before* seeing results:
  - The line is the 25th percentile of premium reviews per 1k women across lounge catchments with a real premium market (10+ premium salons), at baseline levels, rounded to the nearest 10.
  - Expected: the GROW count rises from 4.
  - BT4 negative controls stay SKIP.
  - In BT3, no PROTECT lounge's own market fails on saturation, though some may still fail on size because of the unit.
  - BT5 is unchanged: it measures the data, not the model.
- **B1–B4, additive changes:** no label changes. B3 may raise the low-confidence count.

### Run 2 against the expectations

| Expected | Actual | |
|---|---|---|
| A1: shahama SHRINK → HOLD (~0.32 → 0.38) | 0.318 → 0.383 | met |
| A1: no other lounge changes label | 5 composites move ≤ 0.015; no labels change | met |
| A1: airport cells become growth areas | 0 new: every airport cell is also reached by a scored lounge | not met (vacuous) |
| A2/A3: 7 industrial WATCHes → SKIP | 6 of 7, all through the name rule (A2 caught none); DIP stays WATCH | partly met |
| A2/A3: no GROW changes | none | met |
| A4: no lounge label changes | none | met |
| A4: al-dhafra and al-falah move < 0.1 | al-falah +0.086; al-dhafra +0.100 | al-dhafra on the boundary |
| D1: GROW rises from 4 | 5 (al-jerf); 5 SKIP → WATCH as a side effect | met, barely |
| D1: BT4 stays SKIP | see A2/A3 | partly met |
| D1: no PROTECT market fails on saturation in BT3 | catchments 113–145 < 150: yes; neighbourhood unit: no (size) | partly met |
| D1: BT5 unchanged | identical | met |
| B1–B4: no label changes | none | met |

What we learned: size, not saturation, is the constraint that binds for growth. The recalibration was right, but it mostly removed a contradiction rather than changing the answer.

## Run log

| Run | Date | Trigger | User stories | Back-tests | Sanity checks | Unexplained failures |
|---|---|---|---|---|---|---|
| 0 | 2026-10-10 | Rubric pass 1 (checks run ad hoc by the audit, not as a set) | 1/10 | BT2–BT4 partly run; all fail | SC2 reported; SC5 fails | BT2/BT3 saturation contradiction, BT4 industrial WATCHes, SC5 |
| 1 | 2026-10-10 | Rubric pass 2, after the non-model fixes (docs, UI, explanations) | 2/10 | BT2, BT3, BT4 fail; BT5 run, which falsifies saturation-as-penalty; BT1 not runnable | SC2, SC5 pass; SC1, SC4 partial; SC3 fails; SC6 not runnable | BT2/BT3 (models disagree, PROTECT sites read as SKIP), BT4/SC3 (WORKER_CAP bug), BT5 (MO11), SC4 latent bugs, airport counted as sibling and substitute (decides shahama's SHRINK) |

| 2 | 2026-10-10 | Rubric pass 3, after the non-structural model fixes (A1–A4, B1–B4, D1) | 3/10 | BT2, BT3 explained fails (unit); BT4 partial, explained (DIP); BT5 explained fail (tilt reduced, not removed) | SC2, SC5 pass; SC1, SC3 partial; SC4 fails | **SC4: a new competitor flips al-maqta SHRINK → HOLD** (the coverage-k median bug) |

*Not yet automated:* the checks are run by hand or by agents for now. Scripting BT2–BT5 and SC2–SC4 (as `just sanity`) belongs with the OB3 model work, since BT1 and SC6 only become meaningful after it.
