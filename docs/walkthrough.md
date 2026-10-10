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

> **Of 23 scored lounges, 3 are PROTECT, 15 HOLD and 5 SHRINK, and 5 of 413 growth areas pass both
> tests to GROW.**

Five numbered arguments follow (where to investigate, where to grow, what to protect, how sure we
are, what this can't see), each with its data underneath, then **So what** ("About 262,000 women
live in the 5 GROW areas, beyond a 15-min drive of every lounge, while 5 lounges need a closer look;
with 10 low-confidence calls, this is a shortlist to test, not a set of decisions.") and **Now what**.

Below it, three at-stake figures, counted in women because the model has no money:

| Metric | Value | Counts |
|---|---|---|
| Under pressure: 5 SHRINK lounges | 233,883 women | women in their catchment cells that a sibling also reaches |
| To defend: 3 PROTECT lounges | 203,096 women | women within a 15-min drive of al-ain, al-taif-mall, ras-al-khaimah |
| To grow: 5 GROW areas | 261,797 women | addressable women beyond a 15-min drive of every lounge; 36 more areas on WATCH |

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
signal scores, shared catchment, capture share, premium reviews per 1k women (the growth areas'
saturation measure, shown, not scored), rating, reviews and confidence (filter by Call or Emirate;
click a header to sort). The **Growth areas, ranked** tab lists GROW then WATCH by addressable women
with a one-line *Why* and a confidence.

## 3. One lounge decision: delma (SHRINK)

Click the **delma** flag on Abu Dhabi island, or open
[`?lounge=delma`](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/?lounge=delma).
The map draws its drive polygon, catchment cells and premium substitutes, and a panel opens under
the legend with the short pyramid, **Top drivers:** cannibalisation 0.02 (weight 1) · capture 0.14
(weight 1), and the caveats. Click **Open the lounge page →**
([`/lounge?lounge=delma`](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/lounge?lounge=delma)).

**What.** Kim Tower, Delma Street, Al Nahyan, Abu Dhabi; 4.6★ from 676 Google reviews. *Composite
0.23 · confidence high · the call changes in 0 of 81 assumption combinations.* The AI headline:

> **SHRINK: 98% of Delma's 93,200 catchment women are also reached by a sibling, and it holds 2% of
> a crowded premium market.**

Two arguments, in the order the code ranked them: **Cannibalisation** ("98% of its catchment women
live in cells another Bedashing lounge also reaches.") and **Capture** ("Against 29 premium
substitutes in a pool of 114 it holds 2% of premium reviews, in a market with 587 premium reviews
per 1k women.").

**So what.** "About 1,900 women captured by the review proxy, almost all in cells a sibling also
reaches, in a market far over the 150 premium reviews per 1k women a growth area must stay under.
The call holds in all 81 assumption combinations."

**Now what.** "Investigate, don't close: before the lease event, review whether to downsize or
consolidate into the sibling that shares most of its catchment. It is 0.12 below the HOLD line;
only shared catchment falling to 55% would make it HOLD."

**Drivers.** Scroll to the factor table at the bottom. The contribution rows sum to the composite:
demand 0.13, rating 0.05, capture 0.04, cannibalisation 0.01, which is 0.23. Its market is
mid-sized (93,190 women, demand score 0.47); almost all of it is shared and it holds a tiny slice of
a very crowded one.

**Counterfactual.** Above the table, **What would change the call**: "Composite 0.23 is 0.12 from
the HOLD line. On its own, shared catchment would have to reach 55% of catchment women (now 98% of
catchment women) to make it HOLD."

**Who it shares with.** The **Shared catchment** table names the siblings: khaleej-al-arabi reaches
73% of delma's women, ministries-complex 69%, al-maqta 47% (a HOLD by only 0.003). khaleej-al-arabi is itself SHRINK, so
the consolidation question is about the pair, not one lounge.

**Caveats and confidence.** The blue box beside the call: confidence high, no observed rents
outside Dubai, no revenue or footfall data. Unlike most calls near a line, this one doesn't move
with the assumptions. The sources caption under the table dates every input (Google Places
2026-10-08/09, WorldPop 2025, Mapbox midday traffic, DLD rents).

**Contrast: khalifa-city-a (HOLD).**
[`/lounge?lounge=khalifa-city-a`](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/lounge?lounge=khalifa-city-a)
is just as overlapped (97% shared) but stays HOLD, at composite 0.43 with medium confidence:
"Khalifa City A holds 13% of premium reviews, enough to offset 97% of its catchment being shared
with siblings." Capture contributes 0.24 of its 0.43. So the COO's lease-review list is delma, with
its siblings named and finance's P&L for each before anyone says "close".

## 4. One growth opportunity: Kalba (GROW)

Back on the Overview, open the **Growth areas, ranked** tab: Kalba is rank 4 of 5 GROWs. Click its
blue cells on the east coast, or open
[`/area?area=kalba-sharjah`](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/area?area=kalba-sharjah).

> **GROW: Kalba passes both tests, with about 27,600 women and 44 premium reviews per 1k women.**

Arguments: **Size** (about 27,600 addressable women, 7,638 above the 20,000 line), **Competition** (6
premium salons, 44 premium reviews per 1k women, 106 under the 150 line), **Distance to a lounge**
(al-taif-mall, 12 km in a straight line, beyond a 15-min drive).

**So what.** "About 27,600 women 15+ no lounge reaches today, 83% of them searched, with room under
the saturation line: a lounge here would add to the network's market rather than split a sibling's.
High confidence."

**Now what.** "Start a site search here: a shortlist for a site visit and lease search, verified on
the ground before committing. It would drop to WATCH if addressable women fell by 7,638, or if
premium saturation rose by 106 reviews per 1k women."

**How this call was made** shows the three tests as ✅ (big enough, unsaturated, enough of its women
searched), and **What would change the call** gives both margins, both 20%+ clear of their lines
(high confidence). The caveats: 83% of its women searched, no rents outside Dubai, a
straight-line distance, and Bedashing's only Sharjah lounges (al-jada, zawaya-walk) are on the
Dubai side, which is a business question the model can't answer.

The newest GROW is
[Al Jerf, Ajman](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/area?area=al-jerf-ajman): 23,851 addressable women and 11 premium salons at
59 premium reviews per 1k women. It was a WATCH under the old saturation line of 50 and passes the
recalibrated line of 150 (section 6).

For a WATCH, compare
[`/area?area=al-dhahir-abu-dhabi`](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/area?area=al-dhahir-abu-dhabi):
fully searched, one premium salon, but 10,455 addressable women, 9,545 short. "Don't act now:
revisit if the market grows by about 9,500 addressable women."

## 5. The AI layer

**What Claude does.** Turns a fixed fact sheet into a pyramid: headline, 2-5 arguments with 2-5
data points each, so what, now what. It doesn't make or change calls.

**How it's grounded** (`src/explain.py`):

- `prioritize` decides which arguments appear and in what order (for delma: cannibalisation,
  then capture). The model can't pick its own.
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
time to a lounge** to **20 min (high)**, then click the **mohammed-bin-zayed-city** flag (another
SHRINK, low confidence: it flips in 54 of 81 combinations) and **Open the lounge page →** in its
panel (navigate inside the app: reloading the URL starts a fresh session at the baseline). A
*What-if view* banner appears, mohammed-bin-zayed-city is now HOLD (composite 0.36, up from 0.28),
and its text is captioned *"Template — numbers changed by
the what-if, so the cached AI text no longer applies."* **Reset to baseline** brings the AI text
back. SKIP areas and the NOT SCORED airport lounge always use the template.

## 6. Where not to trust it

These matter more than the calls. The full ranked list is the **How it works & limitations** page
(`docs/limitations.md`).

- **No capacity, no money, no ROIC.** No chairs, hours, utilisation, revenue, rent or capex. The
  model can't tell a full lounge from an empty one or a profitable SHRINK from an unprofitable
  PROTECT. A SHRINK is a prompt to pull the P&L.
- **SHRINK is driven by raw catchment overlap** among the scored lounges, not by services that
  would be lost if a lounge closed. 98% shared says delma's women *could* reach a sibling, not that
  they would, or that the sibling has room.
- **A fix changed a call.** shahama was SHRINK in the first version of this walkthrough (composite
  0.32, 87% shared). Part of that was the NOT SCORED airport lounge, which still counted as its
  sibling and as one of its premium substitutes. The sanity checks flagged it; taking the airport
  out of every comparison made shahama a low-confidence **HOLD** (0.38, 82% shared, 0.03 above the
  line). It happened again: sanity check SC4 found that the rating gap compared a lounge with its
  top-k substitutes' median, and k grows with the pool, so adding a strong competitor could raise a
  lounge's score. The gap now uses the median of the whole premium pool (salons with 20+ reviews).
  That moved al-maqta from SHRINK to **HOLD** at 0.353, 0.003 above the line: a knife-edge call,
  flagged low confidence. A call that rests on a modelling choice is exactly what this list is for.
- **The growth saturation line is still calibrated on our own lounges.** It was 50 premium reviews
  per 1k women, below every lounge market with 10+ premium salons (88+), so GROW only went to near-empty places.
  A back-test (BT5 in `SANITY_CHECKS.md`) found that clustering doesn't hurt premium salons, so the
  line moved to 150: the 25th percentile of the lounge catchments with a real premium market, by a
  rule fixed before seeing the result. That added Al Jerf and narrowed the tilt toward empty areas
  without removing it: the five GROWs run 5-59, and 150 is still judgement. GROW is a shortlist for
  site visits, not evidence of a market.
- **Calls move with assumptions.** 10 of 23 lounge calls are low confidence; mohammed-bin-zayed-city
  flips in 54 of 81 combinations, al-barsha and city-walk in 27.
- **Capture rests on lifetime Google reviews**, so new lounges look weak. **Affluence is observed in
  Dubai only**: every lounge and area in this walkthrough is weighted neutral.
- **Midday drive times, no distance decay**, and a competitor search that misses smaller salons where
  Google's 20-result cap bites.
