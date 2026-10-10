# Walkthrough

About ten minutes. It follows one question from the overview to two decisions, shows how the AI
text is made and checked, and ends with where not to trust it. Every number below is what the app
shows at the baseline (15-min drive, 60% competitor coverage, 5.5% women in worker housing,
affluence weighting medium).

Live app: https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/

## 1. Who it's for and what it decides

The reader is Bedashing's **COO**, who is accountable for lounge operations and return on capital.
The app answers the two decisions the COO already makes:

- **Lease renewal**, lounge by lounge: **PROTECT** (keep and defend), **HOLD** (no action this
  cycle), **SHRINK** (investigate downsizing or consolidating before the lease event, *not* close).
- **Site search**, for expansion: areas beyond a 15-min drive of every lounge are **GROW** (start a
  site search), **WATCH** (revisit when a named test changes) or **SKIP**.

The rules make every call. Claude only explains them, and every number it writes is checked
against the data.

## 2. The overview: the question and what's at stake

Open the [Overview](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/). It opens on the
COO's question, **"Where is my network under pressure, and where should we grow?"**, and answers it
in the **Executive summary**:

> **Of 23 scored lounges, 3 are PROTECT, 13 HOLD and 7 SHRINK; 4 growth areas, all in Sharjah
> emirate, pass both tests to GROW.**

Five numbered arguments follow (where to investigate, where to grow, what to protect, how sure we
are, what this can't see), each with its data underneath, then **So what** ("The pressure is
self-inflicted overlap: every SHRINK lounge shares most of its women with a sibling, while the three
PROTECT lounges have their markets to themselves.") and **Now what**.

Below it, three at-stake figures, counted in women because the model has no money:

| Metric | Value | Counts |
|---|---|---|
| Under pressure: 7 SHRINK lounges | 241,619 women | women in their catchment cells that a sibling also reaches |
| To defend: 3 PROTECT lounges | 203,096 women | women within a 15-min drive of al-ain, al-taif-mall, ras-al-khaimah |
| To grow: 4 GROW areas | 218,300 women | addressable women beyond a 15-min drive of every lounge; 37 more areas on WATCH |

Then the **⚠️ Before you trust these calls** box (no money in the model, lifetime reviews, Dubai-only
affluence, 10 of 23 calls low confidence, growth areas a first cut) and the
**🧪 What if…?** panel (used in section 5).

**The map.** Under *The map — click a lounge or an area*, tick **All catchments (overlap)**. Every
lounge's 15-min catchment is drawn at once, with cells shared by 2+ lounges in red. Abu Dhabi
island and its mainland suburbs are almost solid red; al-ain, al-taif-mall and ras-al-khaimah sit
alone. That is the whole SHRINK story in one picture. Untick it; the other toggles are
**Growth areas** (on), **…including SKIP areas**, **Affluence (Dubai rents)**, **Premium
substitutes** (on) and **…of every lounge**. Hollow circles are low-confidence calls.

**Compare.** At the bottom, the **Lounges** tab ranks every lounge by composite with its four
signal scores, shared catchment, capture share, rating, reviews and confidence (filter by Call or
Emirate; click a header to sort). The **Growth areas, ranked** tab lists GROW then WATCH by
addressable women with a one-line *Why*.

## 3. One lounge decision: shahama (SHRINK)

Click the **shahama** flag north-east of Abu Dhabi island, or open
[`?lounge=shahama`](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/?lounge=shahama).
The map draws its drive polygon, catchment cells and premium substitutes, and a panel opens under
the legend with the short pyramid, **Top drivers:** cannibalisation 0.13 (weight 1) · rating 0.17
(weight 0.5), and the caveats. Click **Open the lounge page →**
([`/lounge?lounge=shahama`](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/lounge?lounge=shahama)).

**What.** Deerfields Mall, Al Shahama Road, Abu Dhabi; 4.6★ from 757 Google reviews. *Composite 0.32
· confidence low · the call changes in 63 of 81 assumption combinations.* The AI headline:

> **SHRINK Shahama, to investigate: 87% of its 66,000 women are shared with siblings in a modest
> market.**

Three arguments, in the order the code ranked them: **Cannibalisation** (87% shared, score 0.13),
**Demand** (about 65,800 women, score 0.33), **Rating vs rivals** (4.6 against the substitutes' 4.8
median).

**So what.** "It holds about 9% of premium reviews, roughly 5,600 customers by the review proxy, but
most of its market is also within a sibling's reach. The call changes in 63 of 81 assumption
combinations, so treat it as low confidence."

**Now what.** "Investigate, don't close: before the lease event, review whether to downsize or
consolidate into the sibling that shares most of its catchment. It is just 0.03 below the HOLD
line, which it would reach if shared catchment fell to 76%."

**Drivers.** Scroll to the factor table at the bottom. The contribution rows sum to the composite:
capture 0.16, demand 0.09, cannibalisation 0.04, rating 0.02, which is 0.32 before rounding each part. Capture is its best signal;
overlap and a modest market drag it under 0.35.

**Counterfactual.** Above the table, **What would change the call**: "Composite 0.32 is 0.03 from
the HOLD line. On its own, shared catchment would have to reach 76% of catchment women (now 87% of
catchment women) to make it HOLD."

**Who it shares with.** The **Shared catchment** table names the siblings: khalifa-city-a reaches
80% of shahama's women, noya-plaza 68%, westyas 59%. (The top row is the airport lounge at 85%; see
section 6.)

**Caveats and confidence.** The yellow box beside the call: within 0.05 of the SHRINK line, flips in
63 of 81 combinations, no observed rents outside Dubai, no revenue or footfall data. The 63 is
real: shahama is SHRINK only at the 15-min drive. At 10 or 20 minutes it is HOLD. The sources
caption under the table dates every input (Google Places 2026-10-08/09, WorldPop 2025, Mapbox
midday traffic, DLD rents).

**Contrast: khalifa-city-a (HOLD).**
[`/lounge?lounge=khalifa-city-a`](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/lounge?lounge=khalifa-city-a)
is *more* overlapped (100% shared) but stays HOLD, at composite 0.41 with medium confidence:
"a strong 12% share of premium reviews, but every one of its 91,000 women is also reached by a
sibling." Capture contributes 0.23 of its 0.41. So the COO's lease-review list is shahama with
khalifa-city-a named as the consolidation partner, and finance's P&L for both before anyone says
"close".

## 4. One growth opportunity: Kalba (GROW)

Back on the Overview, open the **Growth areas, ranked** tab: Kalba is rank 4 of 4 GROWs. Click its
blue cells on the east coast, or open
[`/area?area=kalba-sharjah`](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/area?area=kalba-sharjah).

> **GROW: Kalba has about 23,500 addressable women, 3,500 above the 20,000 line, and a premium
> market under the saturation line (44 reviews per 1k women).**

Arguments: **Size** (23,464 addressable women vs the 20,000 line), **Competition** (6 premium salons,
44 reviews per 1k women, 5.9 under the line of 50), **Distance to a lounge** (al-taif-mall, 11.1 km
in a straight line, beyond a 15-min drive).

**So what.** "About 23,500 women on the east coast are out of the network's reach, enough to carry a
lounge, facing a premium market of only 6 salons; any lounge here would win customers no sibling
already serves."

**Now what.** "Start a site search here: a shortlist for a site visit and lease search, verified on
the ground first. Both margins are thin: 3,500 fewer addressable women or 5.9 more premium reviews
per 1k would drop it to WATCH."

**How this call was made** shows the three tests as ✅ (big enough, unsaturated, 98% of women
searched), and **What would change the call** gives both margins. The caveats say it plainly: near
the saturation line, which "was set from the data it judges"; no rents outside Dubai; and
Bedashing's only Sharjah lounges (al-jada, zawaya-walk) are on the Dubai side, which is a business
question the model can't answer.

For a WATCH, compare
[`/area?area=al-dhahir-abu-dhabi`](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/area?area=al-dhahir-abu-dhabi):
fully searched, one premium salon, but 10,455 addressable women, 9,545 short. "Don't act now:
revisit if the market grows by about 9,500 addressable women."

## 5. The AI layer

**What Claude does.** Turns a fixed fact sheet into a pyramid: headline, 2-5 arguments with 2-5
data points each, so what, now what. It doesn't make or change calls.

**How it's grounded** (`src/explain.py`):

- `prioritize` decides which arguments appear and in what order (for shahama: cannibalisation,
  demand, rating). The model can't pick its own.
- `verify` rejects an explanation unless the arguments are exactly the ranked ones, every cited value
  matches the fact sheet, every number in the prose is a fact or a published threshold (correctly
  rounded), the headline names the call before any other label, *now what* gives the call's
  action, and nothing strays into in-branch advice (staffing, service quality).
- What it can't check: adjectives. "Strong" or "modest" are unverified.

**Offline, no API spend.** The 65 committed explanations in `data/explanations/cache.json` were
written in a Claude Code session from the same prompts the API would get:
`python -m src.explain prompts DIR` → write answers → `check DIR` → `ingest DIR`, which runs
`verify` again and caches only grounded answers. `just explain` is the API route (needs a key).
Every AI text in the app is captioned *"AI-written (cached): every number in it was checked against
the data."*

**Fallback.** The cache is keyed by a hash of the exact numbers. Change them and the cached text no
longer applies, so a deterministic template takes over. Try it: in **🧪 What if…?** set **Travel
time to a lounge** to **20 min (high)**, then click **Open the lounge page →** in shahama's panel
(navigate inside the app: reloading the URL starts a fresh session at the baseline). A *What-if view* banner appears,
shahama is now HOLD (composite 0.39), and its text is captioned *"Template — numbers changed by
the what-if, so the cached AI text no longer applies."* **Reset to baseline** brings the AI text
back. SKIP areas and the NOT SCORED airport lounge always use the template.

## 6. Where not to trust it

These matter more than the calls. The full ranked list is the **How it works & limitations** page
(`docs/limitations.md`).

- **No capacity, no money, no ROIC.** No chairs, hours, utilisation, revenue, rent or capex. The
  model can't tell a full lounge from an empty one or a profitable SHRINK from an unprofitable
  PROTECT. A SHRINK is a prompt to pull the P&L.
- **SHRINK is driven by raw catchment overlap**, not by services that would be lost if a lounge
  closed. 87% shared says shahama's women *could* reach a sibling, not that they would, or that
  the sibling has room. The overlap also counts the **airport lounge**, which is NOT SCORED because
  it serves travellers. It also counts as one of shahama's premium substitutes. Dropping it from the
  overlap alone gives 82% shared, still above the 76% HOLD line. Removing it entirely (overlap
  *and* substitutes) turns shahama into **HOLD** (0.32 → 0.38). So shahama's SHRINK partly rests on
  a lounge that shouldn't be in the comparison. It's a known bug, and the airport shouldn't be
  offered as a consolidation partner either.
- **The growth saturation line sits below every operating lounge's market.** Kalba passes at 44
  premium reviews per 1k women against a line of 50; the factor table notes that lounge catchments
  run 88+. The back-test in `SANITY_CHECKS.md` (BT2) puts our own lounges at 88-629, so the growth
  rule would refuse the markets Bedashing already operates in successfully, al-ain included. GROW
  therefore favours places with almost no premium salons. It is a shortlist for site visits, not
  evidence of a market.
- **Calls move with assumptions.** 10 of 23 lounge calls are low confidence; shahama flips in 63 of 81
  combinations.
- **Capture rests on lifetime Google reviews**, so new lounges look weak. **Affluence is observed in
  Dubai only**: every lounge and area in this walkthrough is weighted neutral.
- **Midday drive times, no distance decay**, and a competitor search that misses smaller salons where
  Google's 20-result cap bites.
