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
- [ ] **US2. "Why was this decision made?"** From the overview, one click on a lounge or area shows its label, the business reason (what / so what / now what), the top drivers with their weight, and caveats. *Rubric: E1–E4, E6, 1.8*
- [ ] **US3. "Who am I up against here?"** I can see the competitors around any lounge: where they are, how many, how they're rated next to us, and whether the catchment is saturated. *Rubric: Q4, L3, C5, C6*
- [ ] **US4. "Where should we open next?"** A ranked shortlist of GROW areas, each showing the unserved demand it captures, its ROIC gate tier, and the reason. *Rubric: Q2, 2.8, OB3, OB5*

#### Drilling in

- [ ] **US5. "Are these two lounges eating each other?"** For an overlapping pair I can see whether it's cannibalization or healthy density, and why. *Rubric: Q3, 3.6*
- [x] **US6. "Why not here?"** For a WATCH or SKIP area, I can see what's holding it back and what would have to change for it to become GROW. *Rubric: 2.6, 2.7, E2*
- [ ] **US7. "Does this one actually pay?"** For any GROW or PROTECT call I can see the contribution and ROIC estimate, the assumptions behind them, and whether the call survives pessimistic assumptions. *Rubric: OB5*
- [ ] **US8. "How much should I trust this?"** Every recommendation shows its confidence and what data is missing or proxied. *Rubric: E4, DA6*

#### Asking the AI

- [ ] **US9. Plain-English question.** For example, "Which Dubai lounges are under the most pressure and why?" gets a grounded answer in what / so what / now what form, with numbers that match the screens. *Rubric: D1, D2, D4, E6*
- [ ] **US10. "What if?"** For example, "What if margin per visit is 20% lower?" or "What if we weight competition more?". I can see which labels change. *Rubric: 5.5, MO6, OB5*

**Notes from pass 1 (2026-10-10):**

- US1: the summary names the SHRINKs and GROWs, but there's no saturation, no "at stake" figure and no network pressure view.
- US2: the weighted drivers are only on the lounge page, and the text has no now-what (see E6).
- US3: only premium substitutes are shown, and there's no catchment saturation.
- US4 (fail): no ranked GROW list, no unserved-demand figure, no ROIC.
- US5 (fail): the shared-women table never judges cannibalisation against healthy density.
- US7 (fail): there's no money in the model.
- US8: areas have no confidence grade.
- US9 (fail): there's no free-text question box. The AI only explains precomputed calls.
- US10: only the level what-if exists. Margin and weights can't be changed.

---

## 2. Back-tests (does the model rediscover what we know?)

The 24 operating lounges are our only revealed-preference data: Bedashing picked these sites, and they're still open. That's weak evidence. We only see survivors, we see today's market rather than the one each lounge opened into, and existence isn't the same as success. So these are diagnostics to explain, not targets to tune toward.

- [ ] **BT1. Leave-one-out rediscovery.** *(Needs the OB3 served/unserved model.)* For each lounge X: remove it, rerun, and check whether its old catchment shows up as unserved demand.
  - *Expected:* PROTECT lounges are rediscovered as GROW. SHRINK lounges' demand is mostly absorbed by their siblings, so it doesn't light up. HOLD lounges fall in between.
  - *Why:* this is the cleanest test of the services-delivered logic. It's the one back-test with a natural expected answer for every lounge.
- [ ] **BT2. Same-unit scoring.** Score each lounge's site with exactly the unit the growth model uses for a candidate at that spot. Don't use the lounge's full catchment, and don't use a single cell.
  - *Expected:* no PROTECT lounge comes out SKIP, and any WATCH has a stated reason.
  - *Pass 1 (wrong unit, so for reference only):* scored on their 15-min catchments, the lounges come out 22 WATCH ("big but saturated", 88–629 premium reviews per 1k women), 2 GROW (al-dhafra, al-falah) and 0 SKIP. Scored on their own cell, all 24 come out SKIP, which reflects the unit, not the model. The real finding is that the saturation line of 50 sits below every working lounge's market, so the growth model would refuse to enter the markets we operate in successfully.
- [ ] **BT3. Cross-model agreement.** Cross-tabulate each lounge's label against the growth label of its own site (from BT2).
  - *Expected:* PROTECT ↔ GROW, or WATCH for a stated reason other than saturation. A lounge marked SHRINK because of cannibalisation can still sit in a strong market, so any disagreement needs an explanation.
  - *Pass 1:* al-ain is PROTECT but reads as a saturated WATCH. Unexplained (rubric B1, MO8).
- [ ] **BT4. Negative controls.** A fixed list of places that should never be recommended.
  - *Expected:* SKIP, with a sensible reason.
  - *Seed list:* jabal-ali-industrial-3, dubai-investments-park, jebel-ali-north-free-zone, new-industrial-ajman, al-ruways-industrial-city, zayed-military-city, plus open desert and airport cells.
  - *Pass 1:* the first six all come out WATCH, so this fails (rubric 2.9).
- [ ] **BT5. Agglomeration: do salons win by clustering?** Retail bunches up: there's a salon floor in every mall, and capturing demand in a busy hub is easier than in an empty area. Test which force actually dominates in the UAE.
  - *Method, part 1:* for every premium salon, relate its success proxy (review volume and rating) to how many other salons sit near it (same building or mall, within 500 m, within 5 min).
  - *Method, part 2:* check the share of our own lounges and of the top-decile competitors that sit in malls or clusters, against the share of GROW areas with no salon nearby.
  - *Expected (hypothesis):* success rises with local density up to some point. If so, saturation can't be a pure penalty (rubric MO11), and the growth model's tilt toward empty areas is a bug, not a feature.
  - *Confound to state:* malls bring footfall and tourists, and tourists leave reviews, so review volume overstates mall salons (DA7).

---

## 3. Sanity checks (cheap, directional, run often)

- [ ] **SC1. Spot checks.** Known hot markets (Dubai Marina, JLT, Downtown, Al Barsha, Abu Dhabi Corniche) read as high demand and high competition. Known empty or non-residential areas read as SKIP. *Pass 1:* no such check exists.
- [ ] **SC2. Label distribution.** Report the counts on every run, and investigate any big swing that the change doesn't explain. *Pass 1:* lounges 3 PROTECT / 13 HOLD / 7 SHRINK / 1 not scored; areas 4 GROW / 37 WATCH / 539 SKIP.
- [ ] **SC3. Geographic realism.** No GROW or WATCH falls in an industrial, military, free-zone, desert or airport area unless it has a written justification (rubric 2.9; overlaps with BT4).
- [ ] **SC4. Monotonicity.** These should always hold:
  - More demand in a cell never lowers its label.
  - Adding a competitor never raises a label.
  - Closing a sibling never pushes a lounge toward SHRINK.
  - A higher margin assumption never fails the ROIC gate where a lower one passed (OB5).

  These are cheap enough to become unit tests.
- [ ] **SC5. Explanation read-through.** Read 5 random cached explanations: 3 lounges and 2 areas. Each must pass what / so what / now what (rubric E6), and nothing in them should tell the COO to fix something inside a branch (OB4). *Pass 1:* fails. Kalba is a bare "what", and mirdif-35 says "Improving its rating is the lever to watch".
- [ ] **SC6. Orders of magnitude.** *(Needs OB2/OB5.)* Estimated services per lounge fit within plausible capacity (specialists × hours), and the contribution and ROIC figures land in a believable range for UAE salons. Nothing should claim a 300% ROIC.

---

## Run log

| Run | Date | Trigger | User stories | Back-tests | Sanity checks | Unexplained failures |
|---|---|---|---|---|---|---|
| 0 | 2026-10-10 | Rubric pass 1 (checks run ad hoc by the audit, not as a set) | 1/10 | BT2–BT4 partly run; all fail | SC2 reported; SC5 fails | BT2/BT3 saturation contradiction, BT4 industrial WATCHes, SC5 |

*Not yet automated:* the checks are run by hand or by agents for now. Scripting BT2–BT5 and SC2–SC4 (as `just sanity`) belongs with the OB3 model work, since BT1 and SC6 only become meaningful after it.
