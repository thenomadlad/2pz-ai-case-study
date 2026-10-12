# Sanity Checks

[`docs/rubric.md`](rubric.md) asks whether the solution has what it needs. This file asks whether the answers are **believable**: whether a COO can actually use them, whether the model rediscovers what we already know, and whether it fails in the places it should. The rubric is the go/no-go gate, and a clean run of this file is one of its conditions (MO5).

## When to run

- **On every rubric pass.**
- **After any change** to `src/model/`, `src/features/`, `src/market.py`, `data/seed/` or `data/scenarios/baseline.yaml`, run at least the back-tests and SC2–SC4.
- **Before a demo or release,** run everything.

Record each run in the log at the bottom.

## Rules

1. **Write the prediction before running.** Every check below states one. If the expectation changes, change it in a commit of its own, with the reason.
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

  *Run 3:* **PARTIAL, explained.** The al-maqta flip is gone: the rating median runs over the whole premium pool (20+ reviews), and a regression test pins it. No competitor raises any label. The remaining composite rises are al-dhafra and al-falah at +0.014, the thin-market blend by design. The median-premium test is still non-monotone in 32 areas, deferred, with no label effect.

  *Run 2:* **FAIL, unexplained model bug.**
  - The thin-market cliff is gone: one extra salon adds +0.014, against +0.14 before.
  - The median-based premium test is still non-monotone in 32 areas, with no label effect. Deliberately deferred.
  - **New:** adding one unpriced 4.9★ salon (259 reviews) to al-maqta flips it from **SHRINK to HOLD** (0.341 → 0.351). The rating gap is taken over the top-k substitutes, with k from `coverage_k`. The extra salon raises k from 20 to 21 and moves the median from 4.65 to 4.60. The bug was latent; A1 moved al-maqta to 0.01 under the line, which exposed it. Fix: take the median over a fixed set.
- [x] **SC5. Explanation read-through.** Read 5 random cached explanations: 3 lounges and 2 areas. Each must pass what / so what / now what (rubric E6), and nothing in them should tell the COO to fix something inside a branch (OB4). *Pass 1:* fails. Kalba is a bare "what", and mirdif-35 says "Improving its rating is the lever to watch". *Run 1:* **PASS.** The sample was khalifa-city-a, noya-plaza, al-dhafra, madinat-hind-4 and digdaga, and across all 65 there are 0 in-branch hits and no missing so-what or now-what. One overclaim was found and fixed by hand: al-dhahir's "half the market a lounge runs on". *Run 2:* **PASS** on the regenerated cache (64 entries; sample noya-plaza, jumeirah-park, al-ain, al-dhahir, al-bihouth). Some so-whats only restate figures (rubric E6 note).
- [ ] **SC6. Orders of magnitude.** *(Needs OB2/OB5.)* Estimated services per lounge fit within plausible capacity (specialists × hours), and the contribution and ROIC figures land in a believable range for UAE salons. Nothing should claim a 300% ROIC.
- [x] **SC8. Performance.** Record, every run, the cold and warm `src.baseline.run()` time (fresh process; cold = no `.cache/` access table) and the full-suite time (`just test` prints the 10 slowest tests). Flag any that regresses more than 2x against the last row; `tests/test_speed.py` fails a warm run over 8 s or a cold one over 10 s.
  - *2026-10-11, before the numpy allocate:* run() 44 s cold and warm; suite 414 s (172 passed, 4 xfailed).
  - *2026-10-11, after:* run() 4.3 s cold, 4.1 s warm; suite 63 s (174 passed, 4 xfailed). Outputs identical (actions exact, floats within 1e-6).

---

## Predictions for run 2 (written 2026-10-10, before the fixes)

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

## Predictions for run 3 (written 2026-10-10, before the fix)

**The fix (the SC4 bug).** The substitutes' median rating will be taken over the lounge's **whole premium pool**, counting only salons with at least 20 reviews (rubric 4.6). Today it's taken over the top-k by reviews, and k moves with the pool. Capture keeps its top-k, which is already monotone.

- **The SC4 case.** Adding a 4.9★ salon with 259 reviews no longer raises al-maqta, or any lounge. A competitor rated *above* the median can only raise the median, so the gap can only shrink.
- **Labels.** At half weight, 0.1 stars of rating gap moves a composite by about 0.024. Only lounges that close to a line can change: al-maqta (0.009 under SHRINK), ras-al-khaimah (0.014 over PROTECT) and al-barsha (0.016 over SHRINK). Every other label holds. Areas are unaffected, since they have no rating signal.
- **Still allowed.** Adding a competitor rated *below* the median can still raise a label slightly, through the rating gap. That's the signal working as designed: a weaker peer does improve relative standing. If it happens, it gets reported, not treated as a bug.
- **Explanations.** Every lounge whose median moves gets a new fact sheet, so its cached explanation goes stale and is regenerated offline.

## Run 4: growth area = named place (2026-10-10)

**The change.** A growth area is now one area per OSM place name and emirate, contiguous or not. Cells that carry only their emirate's fallback name (no OSM boundary or place within 3 km) make no area at all. They still count in lounge catchments, overlap and population totals. That's 67 populated cells outside every catchment, about 33.8k women.

**Prediction.** This was written *after* a local trial, so it isn't a blind prediction:
- No lounge changes.
- The GROW list is unchanged.
- The fake `dubai-dubai` (scattered fallback cells) disappears.
- A few small same-named pieces add up to WATCH.

**Results:**
- **SC2:** lounges are unchanged at 3 / 15 / 5 / 1. Areas go from 580 to **413**: 5 GROW (same list; sharjah-sharjah is one area, 106k women) / 36 WATCH / 372 SKIP. The dropdown lists 68.
- **BT4:** unchanged. Every control is SKIP except Dubai Investments Park (explained).
- **SC3:** no non-residential name gets past SKIP. **New explained caveat:** habshan is WATCH with 44% worker housing and pieces spanning 39 km. That's the cost of merging by name, disclosed in the limitations. Seven non-SKIP areas span more than 20 km, including the GROW areas sharjah-sharjah (33 km) and al-dhaid (23 km). These are large OSM admin units, so an area is a place, not a site (same as BT2/BT3).
- **Everything else:** unchanged, since lounges didn't move. No unexplained failure.

## Predictions for run 5 (written before the commercial-rent work)

- **No label changes.** Shop rent is display only. Any change to a lounge or area label is a bug.
- **SC7 (new): plausibility.**
  - Dubai's median shop rent per DLD area lands within published ranges for Dubai community and street retail (roughly AED 1,000–3,500/m²/yr). Prime mall areas (Downtown / Dubai Mall) sit above AED 3,500.
  - Fewer than 10% of located shop areas fall outside AED 300–10,000/m².
- **BT6 (new): women per rent vs. the calls.**
  - Within Dubai all 5 lounges are HOLD, so there's nothing to test.
  - Outside Dubai (after Task 3): no expected direction. PROTECT lounges win on exclusivity and capture, not on cost. Report the ranking, and don't tune anything to it.
- **Coverage.** Dubai shop rent covers most of the 5 Dubai lounge sites. Outside Dubai, coverage is the band table only.

**Run 5 results:**
- **Labels: met.** No label changed: lounges 3 / 15 / 5 / 1, areas 5 / 36 / 372. A test pins it.
- **SC7: partly met.**
  - 170 located shop areas, median AED 2,031/m²; across the 136 with 10+ contracts, IQR 1,507–2,496. Only 1.8% fall outside 300–10,000. Within the expected range.
  - **Partly met:** Downtown (Burj Khalifa) is 4,561, above 3,500. Business Bay (2,049) and Dubai Marina (2,260) are not. Their DLD area medians mix street shops with mall units, against JLL's prime super-regional mall rent of about 8,900/m². Explained, limitations 15.
  - **Correction from the final review:** the first build applied a 1% trim across all of Dubai, which cut 43 of Downtown's 191 contracts and halved its median (2,256). That made it look as if area medians wash out even Downtown. The trim is gone.
- **BT6: as expected, no direction.** Women per AED 1k (150 m² assumed):
  - Dubai: al-barsha 898, nad-al-sheba 891, mirdif-35 790, jumeirah-park 545, city-walk 407 (all HOLD; City Walk sits in the Downtown-priced area at 4,561).
  - Abu Dhabi bands: noya-plaza 250 and westyas 235 (both SHRINK), shahama 151 and al-dhafra 127 (both HOLD). The two SHRINKs reach *more* women per dirham than the two HOLDs.
- **Coverage: met for Dubai** (5 of 5). Elsewhere only the 4 banded Abu Dhabi lounges (mall or plaza), so 9 of 23 scored lounges in total.

## Predictions for run 7 (written 2026-10-11, before running)

Model since run 6: served demand (Huff); lounge call = served women (0 → 20k) + site cost index (0.5 → 1.5 vs the emirate's typical site), equal weight; capture, rating and cannibalisation shown, not scored; growth = what-if new lounge (GROW: ≥ 6,000 net new women, worker housing < 50%, cost index ≥ 1 or unknown); areas are now every named place, not only cells outside the catchments; affluence weighting off at baseline. Written from reading the code, before any run.

- **SC2.** Big swings are expected and attributable to the model change, not bugs. Lounges: a typical lounge serves about 6k (score ~0.3) at cost index ~1 (0.5), composite ~0.4, so mostly HOLD with more SHRINK than run 6 and 0–3 PROTECT (needs ~15k+ served at a cheap site). Areas: more than 413 non-NOT areas is not expected (same name rule), but GROW/WATCH can move a lot; expect 5–25 GROW.
- **BT1.** PROTECT lounges' served women are mostly *not* absorbed by siblings (absorbed share < 0.3) and their site reads GROW/WATCH when re-opened; SHRINK lounges are mostly absorbed (> 0.5). Isolated lounges (al-ain, ras-al-khaimah, fujairah) absorb little whatever their call.
- **BT2/BT3.** `what_if_open` at each lounge's own site is now a true same-unit test. Expect no PROTECT site comes out SKIP; SHRINK sites mostly SKIP/WATCH on small net new women (siblings already serve them).
- **BT4 / SC3.** All name-rule controls stay SKIP; Dubai Investments Park may now be GROW/WATCH (residential pockets, net-new test only), explained as in run 2.
- **SC4.** +50% women never lowers a label (served and cost index both rise in served women; but the emirate baseline is a median of lounges, which also rises, so a *relative* drop is possible if only one lounge's cells are scaled: expect no drop when scaling one lounge's own cells). A premium competitor never raises a label (it only takes share). Closing a sibling never lowers a lounge's served women; but it can shift the emirate cost baseline (median over lounges), so a cost-index drop is possible: flag it if it changes a label.
- **SC1.** Hot markets keep high competition readings; empty/non-residential areas SKIP.
- **SC7.** Dubai DLD unchanged from run 5; ADREC and listings medians plausible (AED 500–3,000/m²), < 10% outside 300–10,000.
- **BT5.** Data unchanged: result unchanged. **BT6.** Report only.
- **User stories.** US4 moves to PASS or near (net new women per GROW area); US5 to PARTIAL (cannibalisation what-if); US7 still FAIL (no ROIC).

## Run 7 results (2026-10-11, served-demand model)

Scripts: `src.baseline.run()` plus `src.features.lounges.build` + `scorecard.decide` on in-memory copies of `load_v3()` (no repo code edited). `run()` 5.4 s in a fresh process.

- **SC2: reported, swings attributed.** Lounges **5 PROTECT / 9 HOLD / 9 SHRINK / 1 not scored** (run 6: 3 / 15 / 5 / 1). Areas **34 GROW / 63 WATCH / 464 SKIP = 561** (run 6: 5 / 36 / 372 = 413).
  - All 5 PROTECT are in Abu Dhabi (al-ain 0.97, al-dhafra 0.94, khalifa-city-a 0.92, shakhbout-city 0.75, al-falah 0.68), served 9.5k–18.7k. No Dubai lounge serves over 5.2k (dense premium competition in the Huff split), so Dubai is 2 HOLD / 3 SHRINK. Old PROTECTs al-taif-mall (no cost index: Fujairah has no qualifying area, so cost scores neutral) and ras-al-khaimah (cost index 0.86) are now HOLD.
  - Areas grow from 413 to 561 because an area is now every named place, catchment cells included (what-if lounge replaces "beyond every catchment"). GROW rises from 5 to 34 because the test changed from 20k women + unsaturated to ≥ 6,000 net new women + cost index ≥ 1. 374 of 464 SKIPs are the 5k floor.
- **BT1: run for the first time. Expectation partly not met, explained.** Leave-one-out absorbed share (served.py) is ≤ 0.30 for every lounge: siblings never absorb most of a closed lounge's women, because the freed women go mostly to the ~1,100 premium salons and the outside option. SHRINK no longer means "cannibalised" (cannibalisation isn't scored); it means few served women or a dear site. Rediscovery (close the lounge, open a typical lounge at its site with `what_if_open`, classify with `growth.classify`): PROTECT → GROW 1 (al-dhafra, 22.9k net new), WATCH 3, SKIP 1 (al-ain, see BT2).
- **BT2/BT3: now a true same-unit test. Partly met, explained.** Cross-tab (lounge call → its own site, lounge closed, typical lounge at median reviews and rating): PROTECT → GROW 1 / WATCH 3 / SKIP 1; HOLD → GROW 2 / WATCH 3 / SKIP 4; SHRINK → GROW 1 / WATCH 1 / SKIP 7.
  - The one PROTECT → SKIP is al-ain, on the place floor only: its place (al-markhaniyyah) has 4,984 women, 16 under the 5k floor (the same 16 as run 6). On the what-if itself it nets 10.2k at cost index 1.48, which would be GROW.
  - khalifa-city-a, shakhbout-city and al-falah come out WATCH because a *typical* lounge at their site serves far less than they do (khalifa-city-a: 16.7k served vs 6.1k for a typical lounge at the same spot). Served women scale with the lounge's own lifetime review count, so the demand signal partly measures popularity (finding F2).
  - SHRINK al-jada → GROW: a typical lounge there serves 7.9k against its 5.9k. It's 0.005 under the SHRINK line, and with two Sharjah lounges the baseline is their mean, so one of them always sits below 1x.
- **BT4: partial, explained (unchanged).** 5 of 6 controls SKIP by name. Dubai Investments Park is WATCH (4.5k net new, 4% worker housing), as in runs 2–6.
- **SC3: partial, explained.** Non-SKIP areas with non-residential-looking names or 30%+ worker housing: habshan WATCH (44%, run 4 caveat), Dubai Investments Park and Dubai Investment Park 1 / 2 WATCH (residential pockets, same DIP caveat). No industrial, free-zone, military or airport name gets past SKIP.
- **SC4: FAIL, unexplained model bug (F1).** Run on in-memory data copies:
  - *+50% women in a lounge's own catchment:* its own composite never falls (23 of 23). **But other lounges' labels do:** nad-al-sheba HOLD → SHRINK when al-barsha's or jumeirah-park's catchment grows, and al-falah PROTECT → HOLD when any of 6 Abu Dhabi siblings' catchments grow.
  - *A premium competitor (expensive, 4.9★, 2,000 reviews, 200 m away):* no label or composite rises. **Pass.** But see F3.
  - *Close a sibling:* **10 label moves toward SHRINK.** al-jada closed → zawaya-walk HOLD → SHRINK (0.45 → 0.15). Closing any of 7 Abu Dhabi lounges → al-falah PROTECT → HOLD. noya-plaza or westyas closed → al-maqta HOLD → SHRINK. Plus 66 composite dips without a label change.
  - Mechanism, verified: served women only rise (zawaya-walk 6,046 → 6,146), but the cost index is relative to the emirate's *median lounge*. That moves with siblings, and in Sharjah it switches to the area net-new baseline when one of its two lounges closes (zawaya-walk 1.10 → 0.42).
  - *Areas (+50% women) and the margin/ROIC rule:* not run (no plumbing for areas; no ROIC in the model).
- **SC1: partial (as before).** Hot markets read high competition: Marina 4,126, JLT (cluster Q) 1,954, Downtown 1,049, Business Bay 2,967, Al Barsha 274–934 premium reviews per 1k. All are SKIP on 1.6k–2.6k net new: a new lounge in a crowded market adds little, which is consistent. The Abu Dhabi Corniche has no area by that name. The Dubai Marina anomaly persists (2,052 women, floor SKIP). Empty areas: 374 SKIP on the floor.
- **SC7: partly met.**
  - Per-source medians: DLD Dubai 1,985 (2.1% outside 300–10,000); ADREC Abu Dhabi 1,168 (**10.8% outside**: 82 cells under AED 300, min 165); listings Sharjah 1,121, RAK 819, Ajman 755, UAQ 665, Fujairah 461 (0% outside). Emirate medians fill the rest. All cells: 3.7% outside.
  - The ADREC low tail is mostly rural Al Dhafra and the outskirts (Mzeerʻah 30 cells, Eastern Mahadir 23, Niqa Al Dheeb 10), plus Al Ma'mourah (11), which is not checked. It holds 5% of ADREC-cell adults, and no lounge site is in it (lounge rents ≥ 1,168). It does flatter area cost indexes there: mzeer-ah is GROW at 2.57x. Explained in part.
  - Listings medians equal the emirate fallback by construction (the fallback is the median of the listings cells).
- **BT5: unchanged** (data unchanged). Against the model the tilt to empty areas is stronger. The 34 GROW are mostly inland and east-coast Sharjah, Ajman and outer Abu Dhabi; Dubai's only GROW is al-awir. See F4.
- **BT6: report only.** Cost efficiency is now *scored* (served women per AED 1k of site cost), so BT6 is partly by construction. Women per rent (catchment women) doesn't track the call: al-dhafra has the lowest (114) and is PROTECT, because the call uses served women, not catchment women.
- **SC5: PASS.** Cache regenerated offline (121 entries: uae, 23 lounges, 97 non-SKIP areas), all pass verify(). Read-through of al-barsha, noya-plaza, al-ain, al-awir-dubai, mzeer-ah-abu-dhabi and uae: what / so what / now what present, no in-branch advice. One false claim fixed by hand before ingest (uae so-what: GROW women "beyond a 15-min drive of every lounge"; areas now include catchment cells). Area explanations faithfully restate F4-type magnitudes (al-dhaid 57.9k net new) and GROW calls with 0% competitor search (mzeer-ah, rimah), flagged as low confidence.
- **SC8:** run() 4.9 s cold, 4.4 s warm (fresh processes); suite 63 s (178 passed, 0 xfailed). No regression.
- **User stories: 3/10 (US2, US6, US8)**, unchanged count, read from the app code.
  - US4 is still partial. Net new women now appear in each area's "why" and on the area page, but the overview's GROW table ranked by *area women*, not net new (fixed after this run: it now ranks by net new women with a cost-index column); there's no ROIC tier.
  - US5 is still partial. Shared catchment is listed, and closures are available in the what-if, but `absorbed_share` was not shown in `src/webapp` at the time of the run (fixed after: the lounge page now shows it as the cannibalisation what-if), and nothing judges cannibalisation against density.
  - US1 and US3 are partial as before (stake in women). US7 fails (no ROIC). US9 is skipped (no API spend). US10 has levels and closures, but not weights or margin.

**Model issues found (not fixed):**
- **F1 (unexplained, SC4).** The cost index's baseline is the median of the emirate's own lounges, so a lounge's call moves when a sibling opens, closes or grows. This contradicts the scorecard's own "fixed scales so a lounge's score doesn't move when a sibling opens or closes". It's worst in Sharjah, where 2 lounges sit at the `MIN_BASELINE_LOUNGES` switch.
- **F2 (explained finding).** Huff attractiveness = lifetime Google reviews (ALPHA 1), so served women, the demand signal, largely restates review volume. The same site serves 16.7k for khalifa-city-a and 6.1k for a typical lounge.
- **F3 (explained finding, fragility).** One 2,000-review premium salon 200 m away moves al-dhafra PROTECT → SHRINK (0.94 → 0.07), shahama and ras-al-khaimah HOLD → SHRINK, and al-falah and shakhbout-city PROTECT → HOLD. Thin-market lounges' calls rest on there being no big competitor nearby.
- **F4 (unexplained, model).** In 4 non-SKIP areas net new women exceed twice the area's own women. manama-ajman: 35.1k net new from a place of 5.1k women, by reaching 71 cells through the fitted 12.8 km straight-line 20-min band, in a thin market where the new lounge takes about half of every cell against the outside option. These magnitudes aren't believable as one lounge's draw.

## Predictions for run 8 (written 2026-10-11, before running)

Scope: F4 only, plus the non-model changes since run 7 (`est_customers` out of the lounge fact sheet, the retired growth rule deleted, the level-switch test limit). Hypothesis from run 7: the fitted straight-line 20-min band (12.8 km) over-reaches for what-if sites with no isochrone, inflating net new women. If so, the band reaches more supplier pairs than the real isochrones on the 810 cells that have both, and the 4 areas reach mostly straight-line cells.

## Run 8 results (2026-10-11, F4 diagnosis)

- **The hypothesis is falsified: the fallback band under-reaches, it doesn't over-reach.** On the 810 isochrone cells, straight-line bands reach 16.8k / 44.9k / 86.1k cell × supplier pairs within 10 / 15 / 20 min against 15.7k / 47.5k / 97.7k reached by the real isochrones. Count-matching bands would be 4.8 / 9.0 / 13.9 km, wider than the fitted 5.0 / 8.7 / 12.8 at 15 and 20 min. Tightening the band would make the fallback less like the isochrones, so `served.py` is unchanged and **no area or lounge call changes (34 GROW / 63 WATCH / 464 SKIP; lounges 5 / 9 / 9 / 1)**.
- **F4 is explained: "net new > 2x the area's own women" compares a place with a 20-min catchment.** An area is one named place; a lounge there reaches every cell within 20 min, often in another emirate.
  - al-helio-ajman (18.0k net new from 7.5k women) and al-muwaihat-ajman (11.7k from 5.2k) are in Ajman city. 65% and 84% of the women they reach live in cells with real isochrones, mostly in Sharjah city (155k and 301k women). They take only 7% and 3% of the women they reach, so the fallback is not involved.
  - manama-ajman (35.1k from 5.1k) and mudayrah-ajman (18.7k from 7.4k) are Ajman exclaves. Every cell they reach is straight-line (no lounge nearby, so no isochrones), and most of the women live in another emirate's town: 52.0k of 62.7k for manama (Al Dhaid, Sharjah, 10–12 km away), 18.0k of 34.3k for mudayrah (Dubai). In these thin markets the new lounge takes 54–56% of the women it reaches.
- **What remains is a model property, not the fallback.** A thin-market share of 55% is in line with our own isolated lounges: al-dhafra serves 17.6k of 22.9k catchment women (77%). It's the same outside-option and attractiveness calibration as F2/F3 (ALPHA 1, OUTSIDE_PCTL 50, affluence off at baseline). Also, neighbouring areas claim the same women: manama-ajman's 35.1k and al-dhaid-sharjah's 57.9k both come mostly from Al Dhaid. Each what-if opens one lounge alone, so GROW net-new figures must not be summed across areas.
- **Non-model changes, no call moved:** the lounge fact sheet no longer carries `est_customers`, and the 23 lounge so-whats were regenerated offline to quote served women (121 cached, all grounded). The dead two-test rule is out of growth.py. The level-switch test limit is now 3 s: a new level re-runs level_flips' 82 lounge builds, which take 1.6–1.9 s warm.

## Predictions for run 9 (written 2026-10-11, before running SC4 and the back-tests)

Scope: F1 and F2 fixed by the owner's decisions. **F1 (b):** the cost index compares every lounge and area with one frozen UAE-wide anchor, `COST_ANCHOR` = 14.34 site-served women per AED 1k of site cost (the median scored lounge site at baseline). The emirate / area baseline switch is gone. **F2 (a):** the demand signal is `site_served`, what a typical lounge (median reviews and rating) would serve at the lounge's site with that lounge closed and its siblings and rivals open (`served.site_served`, equal to `what_if_open(closed={b})`). The cost signal uses site_served too, so both scored signals assess the site. The lounge's own served women are context: `performance_vs_site` = served_women ÷ site_served ("The model estimates this lounge is performing 2.7x compared to its site"). The SC2 counts and call diff below were computed before this section was written; the rest are predictions.

- **SC2.** Lounges 10 PROTECT / 4 HOLD / 9 SHRINK / 1 not scored, areas 49 GROW / 48 WATCH / 464 SKIP (see the call diff). Big swings attributed: Dubai sites are dear against a UAE-wide anchor, so Dubai drops; lounges whose own reviews carried them (khalifa-city-a, 2.7x its site) drop; northern-emirate and Fujairah sites rise.
- **SC4 (the F1 check).** Closing a sibling can only change another lounge's cost index through its own site-served women (there's no relative baseline left). Site-served women rise when a sibling closes (one rival fewer), except that the typical lounge (median reviews and rating over open lounges) shifts slightly with each closure, so small dips are possible. Expect **no label move toward SHRINK**; flag any. +50% women in one lounge's catchment can't lower another lounge (no median to rise). A new premium competitor never raises a label. Expect SC4 to **PASS on F1**.
- **Level flips.** site_served depends only on demand (worker share, affluence), not on travel time or coverage, so expect far fewer flips than run 8.
- **BT1.** The served model is unchanged: absorbed share ≤ 0.30 as in run 7.
- **BT2/BT3.** The lounge call and the growth what-if now score the same unit (a typical lounge at the spot). Expect PROTECT sites → GROW or WATCH; SHRINK sites → SKIP or WATCH. Remaining disagreements come from net vs gross (the what-if counts net new women, the lounge signal gross site-served) and the area's 5k place floor.
- **BT4 / SC3 / SC1.** The name rule and size floor are untouched: all controls stay SKIP by name, DIP stays WATCH. The 15 new GROW areas are residential places.
- **SC7, BT5, BT6.** Data unchanged: unchanged results. BT5's empty-area tilt is a little stronger (15 more GROW, none in Dubai).
- **SC5.** All 121 explanations regenerated offline (every fact sheet changed); all must pass `check`, every lounge so-what quotes the performance sentence.
- **SC8.** run() a little faster: level_flips no longer builds areas for the emirates that needed an area baseline.

## Run 9 results (2026-10-11, site-scored model, F1 + F2 fixed)

Scripts: `src.baseline.run()` against a snapshot of the committed run 8 (`0ee05eb`), plus `lounges.build` + `scorecard.decide` with closures, a +50% demand multiplier and an added salon on in-memory copies (no repo code edited for the checks). Anchor: `COST_ANCHOR` = 14.34 site-served women per AED 1k (median of the 23 scored lounges at baseline; median scored cost index now 0.9998).

**Call diff vs run 8** (bold = call changed; 14 of 23 scored lounges change call; composites sorted high to low):

| Lounge | Emirate | Old call (composite) | New call (composite) | Served | Site served | Performance vs site | Cost index old → new |
|---|---|---|---|---|---|---|---|
| al-dhafra | Abu Dhabi | PROTECT (0.94) | PROTECT (1.00) | 17,634 | 22,852 | 0.8x | 2.33 → 5.48 |
| **baniyas** | Abu Dhabi | HOLD (0.57) | **PROTECT** (0.83) | 11,086 | 13,036 | 0.9x | 1.09 → 2.33 |
| al-ain | Abu Dhabi | PROTECT (0.97) | PROTECT (0.75) | 18,652 | 10,173 | 1.8x | 2.71 → 2.68 |
| **shahama** | Abu Dhabi | HOLD (0.54) | **PROTECT** (0.75) | 9,865 | 9,865 | 1.0x | 1.08 → 1.95 |
| **al-taif-mall** | Fujairah | HOLD (0.42) | **PROTECT** (0.72) | 6,828 | 8,980 | 0.8x | – → 3.86 |
| shakhbout-city | Abu Dhabi | PROTECT (0.75) | PROTECT (0.72) | 12,743 | 8,685 | 1.5x | 1.35 → 1.67 |
| **ras-al-khaimah** | Ras Al Khaimah | HOLD (0.36) | **PROTECT** (0.70) | 7,328 | 7,946 | 0.9x | 0.86 → 2.08 |
| **al-jada** | Sharjah | SHRINK (0.34) | **PROTECT** (0.70) | 5,853 | 7,912 | 0.7x | 0.90 → 1.55 |
| al-falah | Abu Dhabi | PROTECT (0.68) | PROTECT (0.70) | 9,510 | 7,866 | 1.2x | 1.38 → 2.07 |
| **zawaya-walk** | Sharjah | HOLD (0.45) | **PROTECT** (0.69) | 6,046 | 7,569 | 0.8x | 1.10 → 1.77 |
| **mohammed-bin-zayed-city** | Abu Dhabi | SHRINK (0.14) | **HOLD** (0.44) | 4,057 | 4,581 | 0.9x | 0.57 → 1.16 |
| **khalifa-city-a** | Abu Dhabi | PROTECT (0.92) | **HOLD** (0.40) | 16,679 | 6,144 | 2.7x | 1.50 → 1.00 |
| mirdif-35 | Dubai | HOLD (0.63) | HOLD (0.37) | 5,214 | 5,388 | 1.0x | 2.79 → 0.98 |
| al-maqta | Abu Dhabi | HOLD (0.39) | HOLD (0.35) | 6,990 | 4,159 | 1.7x | 0.92 → 0.99 |
| noya-plaza | Abu Dhabi | SHRINK (0.03) | SHRINK (0.28) | 1,386 | 4,228 | 0.3x | 0.15 → 0.85 |
| **ministries-complex** | Abu Dhabi | HOLD (0.42) | **SHRINK** (0.23) | 8,398 | 3,919 | 2.1x | 0.91 → 0.77 |
| westyas | Abu Dhabi | SHRINK (0.08) | SHRINK (0.16) | 3,160 | 3,259 | 1.0x | 0.35 → 0.66 |
| **nad-al-sheba** | Dubai | HOLD (0.45) | **SHRINK** (0.08) | 2,229 | 2,670 | 0.8x | 1.28 → 0.52 |
| jumeirah-park | Dubai | SHRINK (0.20) | SHRINK (0.06) | 1,636 | 2,234 | 0.7x | 0.82 → 0.38 |
| al-barsha | Dubai | SHRINK (0.30) | SHRINK (0.05) | 2,180 | 2,192 | 1.0x | 1.00 → 0.34 |
| city-walk | Dubai | SHRINK (0.09) | SHRINK (0.05) | 2,155 | 1,905 | 1.1x | 0.57 → 0.17 |
| delma | Abu Dhabi | SHRINK (0.04) | SHRINK (0.05) | 1,695 | 1,895 | 0.9x | 0.21 → 0.42 |
| khaleej-al-arabi | Abu Dhabi | SHRINK (0.08) | SHRINK (0.03) | 3,083 | 1,359 | 2.3x | 0.40 → 0.32 |

Areas: **15 WATCH → GROW, nothing else moves** (34 → 49 GROW, 63 → 48 WATCH, 464 SKIP). All 15 were WATCH on cost alone and clear the lower UAE-wide anchor (the old Abu Dhabi and Ras Al Khaimah baselines were higher): al-wathbah, al-aamerah, bani-yas, al-muwaij-i, al-sader, al-nahdah, shiab-al-ashkhar, al-khibeesi and al-shahamah (Abu Dhabi); meshairef, muntazy, al-rashidiya and al-muwaihat (Ajman); al-dhait-south and ghalilah (Ras Al Khaimah). GROW by emirate: Abu Dhabi 23, Sharjah 11, Ajman 9, Ras Al Khaimah 5, Dubai 1.

- **SC2: reported, swings attributed.** Lounges **10 PROTECT / 4 HOLD / 9 SHRINK / 1 not scored**. Three movers explain most of it. (1) Dubai: every Dubai site is dear against a UAE-wide anchor (cost index 0.17–0.98), so nad-al-sheba HOLD → SHRINK and mirdif-35 slides to the SHRINK line; under the old baseline Dubai lounges were only compared with each other. (2) Popularity no longer scores: khalifa-city-a PROTECT → HOLD (it serves 16,679, but a typical lounge at its site serves 6,144: **2.7x its site**), ministries-complex HOLD → SHRINK (2.1x). (3) Cheap, under-served sites rise: al-jada SHRINK → PROTECT (0.7x its site; a typical lounge would serve more there than it does), al-taif-mall gets an index for the first time (3.86) and goes to PROTECT, ras-al-khaimah, zawaya-walk, baniyas and shahama to PROTECT.
- **SC4: F1 PASSES; one knife-edge move through a different channel (F5).**
  - *Close a sibling (23 closures):* the cost index of every other lounge now moves exactly with its own site-served women (unit test `test_closing_a_lounge_never_changes_another_lounges_cost_index_except_through_served`). Run 7's 10 label moves are gone. **One remains:** al-maqta HOLD → SHRINK (0.3503 → 0.3487) when al-ain, city-walk, mirdif-35 or ras-al-khaimah closes, none of them near it. Mechanism, verified: the "typical lounge" is the median reviews and rating over the *open* scored lounges, so closing al-ain moves it from 757 to 755 reviews and every site-served figure dips by up to ~12 women. al-maqta sits 0.0003 above the SHRINK line. 166 composite dips of at most 0.0018. **Explained, model property (F5):** the typical lounge, like the anchor, should arguably be frozen. Not changed here: the owner's spec defines it as the what-ifs' median, and freezing it would also change the area what-ifs under closures.
  - *+50% women in one lounge's catchment (23 cases):* no lounge's label drops and no lounge's own composite falls. **Pass** (run 7 failed this through the emirate median).
  - *A premium competitor (expensive, 4.9★, 2,000 reviews, 200 m north of each lounge):* **no label rises**; 12 composites rise by 0.0001 (jumeirah-park, mirdif-35, ras-al-khaimah), in lounges far from the new salon. Not investigated (likely the global outside-option percentile or the imputed stand-ins shifting); below any line. Labels fall in 24 cases: a big rival next door now hits the site score directly (al-dhafra, al-falah, al-jada, ras-al-khaimah, shahama, shakhbout-city PROTECT → HOLD, khalifa-city-a and mirdif-35 HOLD → SHRINK). That is F3's fragility, now on the site rather than the lounge.
- **Level flips:** only al-maqta flips (27 of 81, at 0.3503 on the line); the other 22 flip 0 times. site_served depends on worker share and affluence, not travel time or coverage, as predicted.
- **BT2/BT3: PASS.** Same unit on both sides now (a typical lounge at the site, the lounge closed; GROW rule on net new women ≥ 6,000 and cost index ≥ 1, without the place floor). PROTECT → GROW **10 of 10**; HOLD → WATCH 4; SHRINK → SKIP 8, WATCH 1 (ministries-complex, 3,279 net new). Run 7: PROTECT → GROW 1 / WATCH 3 / SKIP 1. The lounge scorecard and the growth model now agree by construction of the unit, which is what F2 asked for; they still differ in gross vs net (the lounge signal counts site-served women, the what-if net new).
- **BT1:** served model unchanged; absorbed share ≤ 0.30 for every lounge, as in run 7.
- **BT4 / SC3: unchanged.** 5 of 6 controls SKIP by name; Dubai Investments Park WATCH (residential pockets, as runs 2–8). The only non-SKIP area with a non-residential name or 30%+ worker housing is habshan WATCH (44%, run 4 caveat). None of the 15 new GROW areas is non-residential.
- **SC1, SC7, BT6:** data unchanged, results unchanged (BT6 women per rent still doesn't track the call). **BT5:** the empty-area tilt is a little stronger: 49 GROW, one in Dubai (al-awir).
- **SC5: PASS.** 121 explanations regenerated offline (prompt v6: uae, 23 lounges, 97 non-SKIP areas), all pass `check`; `verify()` now also requires every lounge so-what to quote the performance sentence word for word. Read-through of al-barsha, al-jada, al-maqta, manama-ajman, al-wathbah-abu-dhabi and uae: what / so what / now what present, no in-branch advice, performance quoted as context. al-maqta's now-what states the 0.0003 knife edge.
- **SC8:** run() 4.4 s cold, 4.1–4.3 s warm (fresh processes; run 7: 4.9 / 4.4); suite 58 s, 182 passed. Faster, because level_flips no longer builds areas for the emirate baseline.
- **User stories:** unchanged count (3/10). US1 improves: a lounge's pressure now reads as its site, and performance vs site separates a weak site from a weak lounge.

**Model issues after run 9:**
- **F1: fixed.** **F2: fixed** (both scored signals assess the site; performance vs site is context).
- **F3 (explained finding, fragility):** unchanged in kind, larger in reach: one big rival 200 m away moves 6 PROTECT sites to HOLD.
- **F5 (new, explained, minor):** the typical lounge (median reviews and rating of open lounges) drifts with closures, so a closure far away can move a knife-edge call (al-maqta). Fix if wanted: freeze it like the anchor.

## Predictions for run 10 (written 2026-10-11, before running SC4 and the back-tests)

Scope: the owner's decision to judge labels **within each emirate, against its market of salon SITES**, frozen. Reference = the 1,123 real premium competitor salons the served model uses (no imputed, no Bedashing), each with its cell shop rent and the women a typical lounge would serve there with all our lounges open (`data/seed/v3/site_reference.csv`, built once by `scripts/build_site_reference.py` in ~9 s; Dubai 582, Abu Dhabi 304, Sharjah 143, Ajman 38, Ras Al Khaimah 33, Fujairah 18, Umm Al Quwain 5). Demand = `demand_pct`, the site's percentile among its emirate's reference sites (UAE-wide under 50). Cost = `rent_ratio` = emirate median reference rent ÷ site rent, on a frozen P10–P90 scale (0.618 → 0, 1.429 → 1). `COST_ANCHOR` and `cost_index` are gone; served women are no longer in the cost signal. GROW also needs `rent_ratio` ≥ 1 and `demand_pct` ≥ 0.5.

- **SC2.** Already seen while building (so not a blind prediction): lounges **6 PROTECT / 14 HOLD / 3 SHRINK / 1 not scored**, areas **32 GROW / 65 WATCH / 464 SKIP**. Expect every swing to trace to one of two causes: Dubai sites now compete with Dubai salon sites (they were dear against a UAE-wide anchor), so Dubai rises; Abu Dhabi and Sharjah sites whose rent is above their emirate's salon-site median fall (their old cost index was high because they served many women per dirham, which the demand signal now carries alone).
- **SC4 (must pass).** *Close a sibling:* `rent_ratio` never moves (emirate median of a frozen set); the demand reference never moves, so `demand_pct` moves only with the lounge's own site-served women (unit test `test_closing_a_lounge_never_moves_another_lounges_reference`). Closing a sibling raises site-served women (one supplier fewer) except through F5 (the typical lounge's median reviews drift with closures). Expect **no label move toward SHRINK**; khaleej-al-arabi (0.3504) sits on the line, so any move there must trace to F5. *+50% women in one catchment:* the reference is frozen, so another lounge can't fall; expect no label drop. *A big premium rival next door:* can only lower site-served women; expect no composite rise beyond float noise and label drops as in run 9 (F3).
- **Level flips.** The reference is frozen at baseline levels while site_served moves with worker share and affluence, so expect somewhat more flips than run 9's single knife edge, concentrated in lounges near a line.
- **BT2/BT3.** Same unit both sides; the growth rule now also needs `rent_ratio` ≥ 1 and `demand_pct` ≥ 0.5, which a PROTECT site mostly has. Expect PROTECT → GROW for most of the 6 (a Dubai PROTECT may miss the 6,000 net line: Dubai sites serve fewer women in absolute terms), SHRINK → WATCH or SKIP.
- **BT4 / SC3 / SC1 / SC7 / BT5 / BT6.** Name rule, size floor and data unchanged: same results; GROW is a subset of run 9's, so no new non-residential GROW.
- **SC5.** 121 explanations regenerated offline (prompt v7); all must pass `check`; read-through of six.
- **SC8.** run() unchanged (~4.2 s warm): one cached CSV read and a sorted search per site.

## Run 10 results (2026-10-11, salon-site reference)

Scripts: `src.baseline.run()` against a snapshot of run 9 (`b3f89a4`), plus `lounges.build` + `scorecard.decide` with closures, a +50% demand multiplier and an added salon on in-memory copies (no repo code edited for the checks). Reference: 1,123 sites, built in 8.6 s; rent-ratio scale P10 0.6176 / P90 1.4290.

**Call diff vs run 9** (bold = call changed; 15 of 23 scored lounges change call; sorted by new composite):

| Lounge | Emirate | Old call (composite) | New call (composite) | Demand pct (ref) · UAE | Rent ratio · rent pct UAE | Old cost index |
|---|---|---|---|---|---|---|
| al-taif-mall | Fujairah | PROTECT (0.72) | PROTECT (0.95) | 90% (UAE) · 90% | 1.55 · 0% | 3.86 |
| al-ain | Abu Dhabi | PROTECT (0.75) | PROTECT (0.83) | 95% (Abu Dhabi) · 93% | 1.19 · 22% | 2.68 |
| **mirdif-35** | Dubai | HOLD (0.37) | **PROTECT** (0.79) | 98% (Dubai) · 75% | 1.10 · 58% | 0.98 |
| al-falah | Abu Dhabi | PROTECT (0.70) | PROTECT (0.77) | 83% (Abu Dhabi) · 85% | 1.19 · 22% | 2.07 |
| al-dhafra | Abu Dhabi | PROTECT (1.00) | PROTECT (0.76) | 100% (Abu Dhabi) · 100% | 1.04 · 32% | 5.48 |
| **nad-al-sheba** | Dubai | SHRINK (0.08) | **PROTECT** (0.71) | 68% (Dubai) · 48% | 1.21 · 55% | 0.52 |
| mohammed-bin-zayed-city | Abu Dhabi | HOLD (0.44) | HOLD (0.61) | 59% (Abu Dhabi) · 70% | 1.13 · 26% | 1.16 |
| **shahama** | Abu Dhabi | PROTECT (0.75) | **HOLD** (0.57) | 93% (Abu Dhabi) · 92% | 0.80 · 54% | 1.95 |
| **baniyas** | Abu Dhabi | PROTECT (0.83) | **HOLD** (0.54) | 99% (Abu Dhabi) · 98% | 0.70 · 62% | 2.33 |
| **shakhbout-city** | Abu Dhabi | PROTECT (0.72) | **HOLD** (0.53) | 87% (Abu Dhabi) · 89% | 0.77 · 56% | 1.67 |
| al-maqta | Abu Dhabi | HOLD (0.35) | HOLD (0.52) | 52% (Abu Dhabi) · 67% | 1.03 · 33% | 0.99 |
| **ras-al-khaimah** | Ras Al Khaimah | PROTECT (0.70) | **HOLD** (0.50) | 86% (UAE) · 86% | 0.73 · 23% | 2.08 |
| **jumeirah-park** | Dubai | SHRINK (0.06) | **HOLD** (0.47) | 45% (Dubai) · 34% | 1.02 · 66% | 0.38 |
| **zawaya-walk** | Sharjah | PROTECT (0.69) | **HOLD** (0.41) | 58% (Sharjah) · 83% | 0.81 · 36% | 1.77 |
| **al-barsha** | Dubai | SHRINK (0.05) | **HOLD** (0.39) | 42% (Dubai) · 33% | 0.90 · 83% | 0.34 |
| **noya-plaza** | Abu Dhabi | SHRINK (0.28) | **HOLD** (0.38) | 52% (Abu Dhabi) · 67% | 0.82 · 52% | 0.85 |
| **delma** | Abu Dhabi | SHRINK (0.05) | **HOLD** (0.38) | 38% (Abu Dhabi) · 25% | 0.93 · 40% | 0.42 |
| khalifa-city-a | Abu Dhabi | HOLD (0.40) | HOLD (0.36) | 73% (Abu Dhabi) · 78% | 0.62 · 76% | 1.00 |
| **ministries-complex** | Abu Dhabi | SHRINK (0.23) | **HOLD** (0.36) | 50% (Abu Dhabi) · 65% | 0.79 · 54% | 0.77 |
| **khaleej-al-arabi** | Abu Dhabi | SHRINK (0.03) | **HOLD** (0.35) | 22% (Abu Dhabi) · 11% | 1.01 · 34% | 0.32 |
| westyas | Abu Dhabi | SHRINK (0.16) | SHRINK (0.35) | 45% (Abu Dhabi) · 57% | 0.82 · 52% | 0.66 |
| **al-jada** | Sharjah | PROTECT (0.70) | **SHRINK** (0.34) | 66% (Sharjah) · 85% | 0.63 · 54% | 1.55 |
| city-walk | Dubai | SHRINK (0.05) | SHRINK (0.15) | 30% (Dubai) · 26% | 0.47 · 98% | 0.17 |

Areas: **17 GROW → WATCH, nothing else moves** (49 → 32 GROW, 48 → 65 WATCH, 464 SKIP). All 17 are big enough and clear the demand test (75%–100% of their emirate's salon sites); all 17 fail on rent, being dearer than their emirate's median salon site (rent ratio 0.50–0.95: al-dhahir, al-samhah, bani-yas, mbazzarah-al-khadra, al-wathbah, al-muwaij-i, shiab-al-ashkhar, al-aamerah, al-nahdah, al-sader in Abu Dhabi; al-helio, al-muwaihat, al-rashidiya in Ajman; wasit in Sharjah; al-dhait-south in Ras Al Khaimah), and two Ajman areas (manama 35,094 net new, mudayrah 18,651) at 0.997: their cells take Ajman's emirate-median shop rent (AED 755/m²), a touch above the median at Ajman's salon sites (753). A knife edge made by a fallback value, not by data. GROW by emirate: Abu Dhabi 13, Sharjah 10, Ajman 4, Ras Al Khaimah 4, Dubai 1.

- **SC2: reported, swings attributed (as expected).** Lounges **6 PROTECT / 14 HOLD / 3 SHRINK / 1 not scored**. (1) Dubai rises: judged against Dubai salon sites, mirdif-35 (98th percentile of Dubai sites, rent ratio 1.10) and nad-al-sheba (68th, 1.21) go to PROTECT; jumeirah-park and al-barsha SHRINK → HOLD; city-walk stays SHRINK (rent ratio 0.47, dearer than 98% of UAE salon sites). (2) Dear sites in their own emirate fall: baniyas, shahama, shakhbout-city (Abu Dhabi, rent ratio 0.70–0.80), ras-al-khaimah (0.73), zawaya-walk (0.81) PROTECT → HOLD, and al-jada PROTECT → SHRINK (0.63): run 9's cost index rewarded their many women per dirham, which the demand signal now carries alone. (3) **New, explained finding (F7): the composites bunch in the middle.** A percentile puts the median salon site at 0.5 and a ratio of 1 scores 0.47, so 14 of 23 lounges are HOLD and 9 sit within 0.05 of a line; run 9 had 4 HOLDs. The lines (0.65 / 0.35) were set for the old scales; moving them would be tuning to taste, so they stay and the bunching is reported.
- **SC4: PASS on the frozen reference; one knife-edge move through F5, as predicted.** *Close a sibling (23 closures):* `rent_ratio` and `demand_ref` never move and `demand_pct` always equals the frozen percentile of the lounge's own site-served women (script check and unit test). khaleej-al-arabi (0.3504) goes HOLD → SHRINK (0.3488) when al-ain, al-falah, city-walk, mirdif-35 or ras-al-khaimah closes: the typical lounge drifts from 757 to 755 reviews, its site-served women dip 1,359 → 1,355 and its percentile 21.7% → 21.4%. With the typical lounge pinned, **0 label moves and 0 composite dips** (verified). *+50% women in one catchment (23 cases):* no label drops, no own composite falls. *A 2,000-review 4.9★ rival 200 m north of each lounge (23 cases):* **no composite rises** (run 9 had 12 rises of 0.0001; the frozen reference removed them); labels fall in 23 cases (F3, unchanged in kind).
- **Level flips:** only khaleej-al-arabi flips (27 of 81, on the line); the other 22 flip 0 times. Fewer than expected: the frozen reference didn't add flips.
- **BT2/BT3: PARTIAL, explained (F6, new).** Same unit; GROW rule with rent ratio and demand percentile. PROTECT → GROW 4 of 6 (al-ain, al-dhafra, al-falah, al-taif-mall); **nad-al-sheba → SKIP (2,637 net new) and mirdif-35 → WATCH (5,343)**. HOLD → WATCH 9, SKIP 5; SHRINK → SKIP 2, WATCH 1 (al-jada, big but dear). Cause: the lounge call is now relative to the emirate, but the growth size line stays an absolute 6,000 net new women (owner's spec), and Dubai sites serve fewer women in absolute terms (the median Dubai salon site serves ~2.3k against ~5.9k in Sharjah). A strong Dubai site can be PROTECT and still too small to open. Owner's call whether NEW_SITE_MIN should also be emirate-relative.
- **BT1:** served model unchanged; absorbed share ≤ 0.30, as run 7.
- **BT4 / SC3 / SC1 / SC7 / BT5 / BT6:** unchanged. GROW is a subset of run 9's, so no new non-residential GROW; 5 of 6 controls SKIP by name, Dubai Investments Park WATCH.
- **SC5: PASS.** 121 explanations regenerated offline (prompt v7), all pass `check` and `ingest`. Read-through: al-jada, al-taif-mall, khalifa-city-a, al-dhahir-abu-dhabi, sharjah-sharjah, uae: what / so what / now what present, each cites the emirate and UAE-wide percentiles, no in-branch advice, performance quoted as context.
- **SC8:** run() 4.1 s cold, 3.8 s warm (fresh processes); speed guard green.
- **User stories:** unchanged count (3/10). US1 reads better: "out-serves 98% of Dubai salon sites · 75th percentile UAE-wide" says what a strong Dubai site is without comparing it with Fujairah.

**Model issues after run 10:**
- **F5 (explained, minor):** now the only channel by which a closure moves another lounge (khaleej-al-arabi). Freezing the typical lounge (757 reviews, 4.6★, already written into the reference file's header) would remove it.
- **F6 (new, explained):** emirate-relative lounge calls vs an absolute growth size line: nad-al-sheba PROTECT but its site would be SKIP as a new opening.
- **F7 (new, explained):** composites bunch around the middle on the percentile / ratio scales: 14 HOLD, 9 within 0.05 of a line.

## Predictions for run 11 (written 2026-10-11, before running SC4)

Scope: three owner-approved fixes. (1) **Fallback rents are neutral** (`growth.RENT_FALLBACK_WHY`): an area with half or more of its rented women in emirate-median cells passes the GROW rent test, low confidence, caveat; a lounge whose site cell is on the fallback scores rent 0.5, low confidence. (2) **The typical lounge is frozen** at 757 reviews, 4.6★ (`lounges.TYPICAL_WHY`; site_reference.csv unchanged, built with the same values). (3) The keep-within-emirate vs absolute-growth-floor limitation is stated (F6), no call change.

- **SC2.** Already seen while building: lounges **6 / 14 / 3 / 1** (no call change; al-ain 0.83 → 0.72 and al-falah 0.77 → 0.66 stay PROTECT, now low confidence: 11 low-confidence lounges). Areas **34 GROW / 63 WATCH / 464 SKIP**: manama-ajman and mudayrah-ajman WATCH → GROW (the 0.997 fallback knife edge, F-run 10), nothing else moves. 17 of the 34 GROW are on a fallback rent, all low confidence. sharjah-sharjah (15% fallback) keeps its observed-rent GROW at ratio 1.000.
- **SC4 (must pass, 0 moves).** *Close a sibling (23 closures):* with the typical lounge frozen, F5 is gone: expect **0 label moves and 0 composite dips** in any other lounge (khaleej-al-arabi stays HOLD at 0.3504). *+50% women in one catchment:* no label drop. *A 2,000-review 4.9★ rival next to each lounge:* no composite rise.
- **Level flips:** khaleej-al-arabi still flips (on the line); al-ain and al-falah flip 0 (composite 0.72 / 0.66, but al-falah sits 0.015 above PROTECT, so a few flips there are possible).
- **BT2/BT3:** unchanged in kind (F6): nad-al-sheba still SKIP as a new opening.
- **SC5.** 23 explanations regenerated offline (prompt v7), all pass `check` and `ingest`.
- **SC8.** run() unchanged (~4.4 s); speed guard green without raising limits.

## Run 11 results (2026-10-11, fallback rents neutral, typical lounge frozen)

Scripts: `src.baseline.run()` against a snapshot taken before the change, plus `lounges.build` + `scorecard.decide` with each of the 23 closures, a +50% women multiplier on each catchment and a 2,000-review 4.9★ rival 200 m north of each lounge (in-memory copies; no repo code edited for the checks).

**Call diff vs run 10:**

| Subject | Before | After | Why |
|---|---|---|---|
| manama-ajman | WATCH (high) | **GROW (low)** | 100% fallback rent; 0.997 ratio was the Ajman fallback, now neutral |
| mudayrah-ajman | WATCH (high) | **GROW (low)** | same |
| al-ain | PROTECT 0.829 (high) | PROTECT 0.724 (low) | site cell on the Abu Dhabi fallback: rent 0.71 → 0.5 |
| al-falah | PROTECT 0.769 (high) | PROTECT 0.665 (low) | same; now 0.015 above the PROTECT line |
| al-dhaid, kalba, khor-fakkan, al-hamriya, milehah, al-ramlah, dibba-al-hisn (Sharjah), al-fahlain (RAK) | GROW (high) | GROW (low) | mostly fallback rent |
| al-awir, digdaga, al-sad | GROW (medium) | GROW (low) | mostly fallback rent |

al-madam, al-batayih, ghalilah, khatt were already low (coverage or the size line). sharjah-sharjah (15% fallback) keeps its observed GROW at ratio 1.000: its weighted median lands on the fallback value, its listings cells alone give 0.997 (an explained knife edge, `RENT_FALLBACK_WHY`).

- **SC2: as expected.** Lounges **6 / 14 / 3 / 1** (no call change); areas **34 GROW / 63 WATCH / 464 SKIP**. 17 of 34 GROW are on a fallback rent, all low confidence. GROW by emirate: Abu Dhabi 13, Sharjah 10, Ajman 6, Ras Al Khaimah 4, Dubai 1. 11 of 23 lounges low confidence (9 + al-ain, al-falah).
- **SC4: PASS, 0 violations.** *Close a sibling (23 closures):* **0 moves toward SHRINK and 0 composite dips** in any other lounge; F5 is gone (khaleej-al-arabi stays HOLD 0.3504 under every closure). Four moves *up*, by design (a closed sibling raises a neighbour's site demand): westyas SHRINK → HOLD when al-falah, khalifa-city-a or shahama closes (0.348 → 0.351–0.358), al-jada SHRINK → HOLD when zawaya-walk closes (0.338 → 0.363). My expectation said "0 label moves"; it should have said "0 moves toward SHRINK", which run 10 meant too. Unit test: every closure's site_served opens the same frozen 757-review 4.6★ lounge. *+50% women in one catchment (23 cases):* 0 label drops. *Rival next door (23 cases):* 0 composite rises; 27 label falls (F3, unchanged in kind; run 10 counted 23, not re-diagnosed).
- **Level flips:** khaleej-al-arabi 27/81 only; al-ain and al-falah 0.
- **BT2/BT3:** unchanged in kind (F6; nad-al-sheba SKIP as a new opening). F6 is now stated as a limitation (How page box 6, README, limitations 8, lounge glossary).
- **SC5: PASS.** 23 explanations regenerated offline (prompt v7): 20 fallback areas, al-ain, al-falah, the UAE summary; `check` and `ingest` 23 / 0 failed. Read-through: manama-ajman, kalba-sharjah, al-ain, uae: rent named as the emirate median, not observed, and neutral; no in-branch advice; performance quoted as context.
- **SC8:** run() 4.4 s (fresh processes); suite 57 s (186 passed); speed guard green, limits unchanged.

**Model issues after run 11:** F5 fixed. F6 stated, owner's call unchanged. F7 unchanged. New, explained: sharjah-sharjah's median lands on the fallback value at 15% fallback share.

## Run 12 results (2026-10-11, confidence check over live axes only)

- **Finding** (`src/webapp/data.at_level`): in the served-demand (Huff) model, the travel and coverage levels change no scoring input: site_served, served_women, demand_pct, composite and every lounge and area call are identical at low / medium / high (travel only changes the displayed catchment). Search recall doesn't reach the scoring either (0.4 and 0.9: no composite, site_served or call moves; it feeds capture and premium density, shown not scored). Affluence is off. Only worker share moves calls. So 78 of the 81 combinations repeated the other 3.
- **Change (owner's option b):** `scorecard.LIVE_AXES = ("worker_share",)`, `COMBOS` 81 → 3, `FLIP_LOW` 27 → 1 (still a third). `Levels` unchanged. App: drive-time and coverage selectors and tabs removed; the "Call at 10 / 15 / 20 min" column dropped. Wiring them back is in README, Potential improvements.
- **Confidence diff:** no call and no confidence changed (asserted against a before snapshot): 11 of 23 low before and after. khaleej-al-arabi 27/81 → 1/3 (HOLD, low); every other lounge 0.
- **SC5:** 1 explanation regenerated offline (khaleej-al-arabi, its level_flips fact changed); `check` and `ingest` 1 / 0 failed. Note: one stray paid-API call was made by mistake (`src.explain --help` runs the API path); its cache write was reverted before the offline regeneration.
- **SC8:** run() 4.1–4.4 s → 3.2–3.3 s (fresh processes); suite 44 s (183 passed); speed guard green.

## Run 13 results (2026-10-11, drive time and coverage wired into the Huff split; UI changes)

Lean run: SC2, SC4, SC5, SC8. Back-tests not re-run (the calls didn't change, so BT2-BT6 carry over from run 11).

- **SC2:** calls unchanged: lounges 6 / 14 / 3 / 1, areas 34 / 63 / 464. Confidence over 27 combinations again (run 12: 3): **12 of 23 low** (run 12: 11). New: jumeirah-park, whose call changes in 9 of 27 (a third). Flips now: khaleej-al-arabi 16, khalifa-city-a 15, al-jada 12, nine lounges at 6-9.
- **SC4 (close a sibling, 23 closures): PASS, 0 violations.** 0 moves toward SHRINK and 0 composite dips in any other lounge. The same four moves *up* as run 11, by design: westyas SHRINK → HOLD when al-falah, khalifa-city-a or shahama closes (0.348 → 0.351-0.358), al-jada SHRINK → HOLD when zawaya-walk closes (0.338 → 0.363). Not re-run: +50% women and rival next door (no change to those paths).
- **SC5:** 15 explanations regenerated offline (14 lounges + the UAE summary; the others' fact sheets were unchanged); `check` and `ingest` 15 / 0 failed; the 3 stale-explanation xfails removed and passing. Note: `python -m src.explain --help` again ran the paid-API path (any unknown argument does) before it was killed; its 12 API-written cache entries were reverted and every committed entry is offline-written. The CLI should refuse unknown arguments.
- **SC8:** run() 4.5 s cold (fresh process); 23 closures 73 s (~3.2 s each, every closure re-runs the 27-combination confidence check); suite 147 s (184 passed, 0 xfailed; run 12: 44 s, the 27-combination confidence check is back in every run).

## Run log

| Run | Date | Trigger | User stories | Back-tests | Sanity checks | Unexplained failures |
|---|---|---|---|---|---|---|
| 0 | 2026-10-10 | Rubric pass 1 (checks run ad hoc by the audit, not as a set) | 1/10 | BT2–BT4 partly run; all fail | SC2 reported; SC5 fails | BT2/BT3 saturation contradiction, BT4 industrial WATCHes, SC5 |
| 1 | 2026-10-10 | Rubric pass 2, after the non-model fixes (docs, UI, explanations) | 2/10 | BT2, BT3, BT4 fail; BT5 run, which falsifies saturation-as-penalty; BT1 not runnable | SC2, SC5 pass; SC1, SC4 partial; SC3 fails; SC6 not runnable | BT2/BT3 (models disagree, PROTECT sites read as SKIP), BT4/SC3 (WORKER_CAP bug), BT5 (MO11), SC4 latent bugs, airport counted as sibling and substitute (decides shahama's SHRINK) |

| 2 | 2026-10-10 | Rubric pass 3, after the non-structural model fixes (A1–A4, B1–B4, D1) | 3/10 | BT2, BT3 explained fails (unit); BT4 partial, explained (DIP); BT5 explained fail (tilt reduced, not removed) | SC2, SC5 pass; SC1, SC3 partial; SC4 fails | **SC4: a new competitor flips al-maqta SHRINK → HOLD** (the coverage-k median bug) |

| 3 | 2026-10-10 | The SC4 fix (rating median over the whole premium pool, 20+ reviews) | 3/10 | unchanged from run 2 (explained) | SC4 now partial, explained; others unchanged | **none.** Outcome vs expectation: only al-maqta changed label (SHRINK → HOLD, 0.341 → 0.353), one of the three predicted candidates; ras-al-khaimah moved within PROTECT and al-barsha didn't move. |

| 4 | 2026-10-10 | Growth area = named OSM place; unnamed (emirate-fallback) cells make no area | 3/10 | unchanged (explained) | SC2 reported; SC3 one new explained caveat (habshan) | none |

| 5 | 2026-10-10 | Commercial (shop) rent and women per AED 1k of rent, display only | unchanged | BT6 run, no direction (as expected) | SC7 partly met: Downtown 4,561 above 3,500; Marina and Business Bay area medians mix in street shops (explained). The first build's overall trim was corrected after review | none |

| 6 | 2026-10-11 | Full run after runs 3–5 (median fix, named-place areas, shop rent) | 3/10 (US4 findability regression: the Areas page's default emirates hide every GROW) | BT2/BT3 explained fails (now a true same-unit test: areas are scored on residents, lounges on 15-min catchments; al-ain's place misses the 5k floor by 16 women); BT4 partial (DIP); BT5 unchanged; BT6 no direction | SC2, SC5 pass; SC1, SC3, SC4, SC7 partial, all explained; SC4 cleaner than run 1 (no sibling-closure dips) | **none** |

| 7 | 2026-10-11 | Served-demand (Huff) model: 2-signal scorecard (served women, cost index), growth = what-if new lounge, areas = every named place | 3/10 (US4/US5 partial: net new shown but GROW table ranks by area women; absorbed share not shown) | BT1 first run: absorbed ≤ 0.30 for all (SHRINK ≠ cannibalised; explained); BT2/BT3 same-unit via what_if_open: al-ain SKIP on the place floor only (explained); BT4 partial (DIP); BT5 data unchanged, empty-area tilt stronger; BT6 report | SC2 5/9/9/1, 34/63/464 (attributed); SC4 **FAIL**; SC1, SC3, SC7 partial (ADREC 10.8% < AED 300, rural); SC5 pass (121 regenerated); SC8 4.9 s cold / 4.4 s warm, suite 63 s | **SC4/F1: closing or growing a sibling flips labels via the emirate-median cost baseline (zawaya-walk HOLD → SHRINK when al-jada closes; al-falah PROTECT → HOLD; al-maqta, nad-al-sheba → SHRINK). F4: net new women > 2x area women in 4 areas (manama-ajman 35k from 5k)** |

| 8 | 2026-10-11 | F4 diagnosis; `est_customers` out of the lounge fact sheet; retired growth rule deleted | unchanged (3/10) | unchanged from run 7 | Calls unchanged (5/9/9/1, 34/63/464); SC5 pass (121 regenerated, 23 lounges); suite green | **F1 still open.** F4 explained: the straight-line band under-reaches the isochrones (86k vs 98k pairs at 20 min), and the 4 areas are small places whose 20-min reach covers a neighbouring town (Sharjah city, Al Dhaid, Dubai) |

| 9 | 2026-10-11 | F1 (frozen UAE-wide cost anchor, 14.34) and F2 (site_served demand; performance_vs_site as context) | unchanged (3/10) | BT2/BT3 **pass**: PROTECT → GROW 10/10, SHRINK → SKIP 8 + WATCH 1, HOLD → WATCH 4; BT4 partial (DIP); BT1, BT5, BT6 unchanged | SC2 10/4/9/1, 49/48/464 (14 lounge calls and 15 WATCH → GROW, attributed); SC4 **F1 passes** (no relative baseline; +50% demand never lowers another lounge), one knife-edge closure move via the typical-lounge median (F5); SC5 pass (121 regenerated); SC8 4.4 s cold / 4.1 s warm, suite 58 s | **none unexplained.** F5 (typical lounge drifts with closures; al-maqta 0.0003 from the line) and F3 fragility explained |

| 10 | 2026-10-11 | Labels judged within each emirate against a frozen reference of 1,123 competitor salon sites: demand percentile + rent ratio; GROW also needs rent ratio ≥ 1 and demand ≥ 50th percentile | unchanged (3/10) | BT2/BT3 partial, explained (F6: PROTECT → GROW 4/6; nad-al-sheba SKIP on the absolute 6,000 line); BT4 partial (DIP); BT1, BT5, BT6 unchanged | SC2 6/14/3/1, 32/65/464 (15 lounge calls and 17 GROW → WATCH, attributed; F7 bunching); SC4 **pass** on the frozen reference (rent ratio and reference never move; one F5 knife-edge move, 0 with the typical lounge pinned; no competitor raises a composite); SC5 pass (121 regenerated); SC8 4.1 s cold / 3.8 s warm | **none unexplained.** F5, F6, F7 explained |

| 11 | 2026-10-11 | Fallback rents neutral (area half+ fallback, lounge site cell); typical lounge frozen (757, 4.6★); F6 limitation stated | unchanged (3/10) | BT2/BT3 unchanged (F6, now a stated limitation); others unchanged | SC2 6/14/3/1, 34/63/464 (manama-ajman, mudayrah-ajman WATCH → GROW; al-ain, al-falah PROTECT at low confidence); SC4 **pass** (0 moves toward SHRINK, 0 dips; F5 gone); SC5 pass (23 regenerated); SC8 4.4 s, suite 57 s | **none unexplained.** sharjah-sharjah fallback-median edge explained |
| 12 | 2026-10-11 | Confidence check over live axes only (worker share; travel and coverage don't reach the Huff scoring) | unchanged | unchanged | Calls and confidences unchanged (11 of 23 low); khaleej-al-arabi 27/81 → 1/3; SC5 1 regenerated; run() 3.3 s | none |
| 13 | 2026-10-11 | Drive time and coverage wired into the Huff split (confidence over 27 combinations again); UI: Executive Summary, What-if explorer, table pickers, factor tree | unchanged | not re-run (calls unchanged) | Calls 6/14/3/1, 34/63/464 unchanged; 12 of 23 low (jumeirah-park new, 9/27); SC4 **pass** (0 moves toward SHRINK, 0 dips); SC5 15 regenerated offline; run() 4.5 s cold, suite 147 s | none |

*Not yet automated:* the checks are run by hand or by agents for now. Scripting BT2–BT5 and SC2–SC4 (as `just sanity`) belongs with the OB3 model work, since BT1 and SC6 only become meaningful after it.
