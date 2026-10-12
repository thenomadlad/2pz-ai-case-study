# Walkthrough

About ten minutes. It follows one question from the overview to two decisions, shows how the AI
text is made and checked, and ends with where not to trust it. Every number below is what the app
shows at the baseline on 2026-10-11 (15-min drive, 60% competitor coverage, 5.5% women in worker
housing, affluence weighting off). The AI text is paraphrased, not quoted: it is regenerated when the
model changes.

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
in the **Executive summary**: of 23 scored lounges, 6 are PROTECT, 14 HOLD and 3 SHRINK; 32 of 561
growth areas are GROW and 65 WATCH. Every label is judged within the site's emirate against a frozen
market of 1,123 competitor salon sites, never against our own lounges. Numbered arguments follow (where to investigate, where to grow,
what to protect, how sure we are, what this can't see), each with its data underneath, then **So
what** and **Now what**.

Below it, three at-stake figures, counted in women because the model has a rent-based site cost but
no revenue:

| Metric | Value | Counts |
|---|---|---|
| Under pressure: 3 SHRINK lounges | about 323k women | women in their catchment cells that a sibling also reaches |
| To defend: 6 PROTECT lounges | about 595k women | women within a 15-min drive of them |
| To grow: 32 GROW areas | about 784k women | addressable women beyond a 15-min drive of every lounge; 65 more areas on WATCH |

Then the **⚠️ Before you trust these calls** box (no revenue or lease data, lifetime reviews behind
served demand, shop rent from a different source per emirate, 9 of 23 calls low confidence, growth
areas a first cut) and the **🧪 What if…?** panel (used in section 5).

**The map.** Under *The map — click a lounge or an area*, tick **All catchments (overlap)**. Every
lounge's 15-min catchment is drawn at once, with cells shared by 2+ lounges in red. Abu Dhabi
island and its mainland suburbs are almost solid red; al-ain, al-dhafra, al-taif-mall and
ras-al-khaimah sit alone. Overlap is shown, not scored: the Huff split already divides a shared
cell's women between the lounges and salons that reach it. Untick it; the other toggles are
**Growth areas** (on), **…including SKIP areas**, **Affluence (Dubai rents)**, **Premium
substitutes** (on) and **…of every lounge**. Hollow circles are low-confidence calls.

**Compare.** At the bottom, the **Lounges** tab ranks every lounge by composite with its two
signal scores (demand, rent), and as context its shared catchment, capture share, premium reviews per
1k women, shop rent, rating, reviews and confidence (filter by Call or Emirate; click a header to
sort). The **Growth areas, ranked** tab lists GROW then WATCH with a one-line *Why* and a confidence.

## 3. One lounge decision: city-walk (SHRINK)

Click the **city-walk** flag in Dubai, or open
[`?lounge=city-walk`](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/?lounge=city-walk).
The map draws its drive polygon, catchment cells and premium substitutes, and a panel opens under
the legend with the short pyramid, its top drivers and the caveats. Click **Open the lounge page →**
([`/lounge?lounge=city-walk`](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/lounge?lounge=city-walk)).

**What.** City Walk, Al Wasl, Dubai. *Composite 0.15 · confidence high · the call changes at 0 of 3
worker-housing share levels.* A typical lounge at its site would serve about **1,900 women** in the Huff
split: **bottom 30% of Dubai salon sites on demand** (the demand score is that percentile, 0.30),
26th percentile UAE-wide. Its shop rent, AED 4,561/m² (its DLD area's median), gives a **rent ratio
of 0.47**: Dubai's median salon site pays under half that. That is below the rent scale's P10 (0.62),
so the rent score is 0; it is the 98th percentile of rent UAE-wide. The page also says *The model
estimates this lounge is performing 1.1x compared to its site*: context, not scored.

**The two signals.** *The two signals, on fixed scales* shows each value, its scale, the UAE-wide
percentile beside it and why the scale is set there: both rank the site within its emirate against a
frozen reference of competitor salon sites (582 in Dubai), never against our own lounges. The factor
table at the bottom gives each signal's contribution to the composite. Capture, rating and shared
catchment are shown below them, not scored.

**Who it shares with.** The **Shared catchment** table names the siblings that reach its cells
(72% of its catchment women are also reached by another lounge). If city-walk closed, siblings would
take over about 1% of its served women (the absorbed share): its women would go to premium salons
or the outside option, not to a sibling.

**Caveats and confidence.** The box beside the call: confidence high, no revenue, lease or footfall
data. Its rent is a DLD area median, which mixes mall and street shops, not city-walk's lease; and a
prime rent may be buying footfall the model can't see.

**Contrast: nad-al-sheba (PROTECT).**
[`/lounge?lounge=nad-al-sheba`](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/lounge?lounge=nad-al-sheba)
is even more overlapped (75% shared) but PROTECT at 0.71: top 32% of Dubai salon sites on demand
(48th percentile UAE-wide) at a rent ratio of 1.21, cheaper than the median Dubai salon site.
Overlap alone doesn't make a SHRINK. So the COO's lease-review list starts with city-walk, with
finance's P&L for it before anyone says "close".

## 4. One growth opportunity: Kalba (GROW)

Back on the Overview, open the **Growth areas, ranked** tab. Click Kalba's blue cells on the east
coast, or open
[`/area?area=kalba-sharjah`](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/area?area=kalba-sharjah).

**How this call was made.** Every area is a what-if: open a typical lounge (the median lounge's
reviews and rating) at its centre. In Kalba it would add about **12,500 net new women** (6,000
needed), worker housing is 1% (under 50%), it is in the **top 10% of Sharjah salon sites on demand**
(0.5 needed; 98th percentile UAE-wide), and its **rent ratio is 1.00** (1 needed). All checks ✅,
high confidence. Premium reviews per 1k women is shown as context.
The caveats: Kalba has no shop rent of its own, so it carries Sharjah's emirate median, which equals
the median at Sharjah's reference salon sites: the rent test passes by construction, as it does for
all 10 Sharjah GROW areas. A site far from any salon also tops the demand percentile easily (the
reference sites all have a competitor next door). Distance is a straight line, and Bedashing's only
Sharjah lounges (al-jada, zawaya-walk) are on the Dubai side, which is a business question the model
can't answer.

For a WATCH, compare
[`/area?area=bani-yas-abu-dhabi`](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/area?area=bani-yas-abu-dhabi):
about 8,300 net new women and the top 2% of Abu Dhabi salon sites on demand, but a rent ratio of
0.70, dearer than the median Abu Dhabi salon site (62nd percentile of rent UAE-wide). All 17 WATCH
areas with 6,000+ net new women fail this way, on rent; none fails on demand.

## 5. The AI layer

**What Claude does.** Turns a fixed fact sheet into a pyramid: headline, 2-5 arguments with 2-5
data points each, so what, now what. It doesn't make or change calls.

**How it's grounded** (`src/explain.py`):

- `prioritize` decides which arguments appear and in what order (for a lounge: demand, then cost, by
  how far each sits from neutral). The model can't pick its own.
- `verify` rejects an explanation unless the arguments are exactly the ranked ones, every cited value
  matches the fact sheet, every number in the prose is a fact or a published threshold (correctly
  rounded), the headline names the call before any other label, *now what* gives the call's
  action, and nothing strays into in-branch advice (staffing, service quality).
- What it can't check: adjectives. "Strong" or "modest" are unverified.

**Offline, no API spend.** The committed explanations in `data/explanations/cache.json` were
written in a Claude Code session from the same prompts the API would get:
`python -m src.explain prompts DIR` → write answers → `check DIR` → `ingest DIR`, which runs
`verify` again and caches only grounded answers. `just explain` is the API route (needs a key).
Every AI text in the app is captioned *"AI-written (cached): every number in it was checked against
the data."*

**Fallback.** The cache is keyed by a hash of the exact numbers. Change them and the cached text no
longer applies, so a deterministic template takes over. Try it: in **🧪 What if…?** set **Travel
time to a lounge** to **20 min (high)**, or close a lounge from its map panel, then open a lounge
page from inside the app (reloading the URL starts a fresh session at the baseline). A *What-if
view* banner appears, and where the numbers changed the text is captioned *"Template — numbers
changed by the what-if, so the cached AI text no longer applies."* **Reset to baseline** brings the
AI text back. SKIP areas and the NOT SCORED airport lounge always use the template.

## 6. Where not to trust it

These matter more than the calls. The full ranked list is the **How it works & limitations** page
(`docs/limitations.md`).

- **No capacity, no revenue, no ROIC.** No chairs, hours, utilisation, revenue, actual lease or
  capex. The cost signal is a shop rent against its emirate's median salon site; site cost (an
  assumed 150 m² unit plus an assumed fit-out) is display only. The model can't
  tell a full lounge from an empty one or a profitable SHRINK from an unprofitable PROTECT. A SHRINK
  is a prompt to pull the P&L.
- **Shop rent comes from a different source per emirate**: DLD contracts (Dubai), ADREC district
  rates read by hand off its public map (Abu Dhabi), Property Finder / Bayut asking rents scraped via
  third-party Apify actors, a grey area under those portals' terms (northern emirates), else the
  emirate median. The rent ratio compares a site only with its own emirate's salon sites, and a
  site on the emirate-median fallback lands at a ratio of about 1.
- **Served demand rests on lifetime Google reviews** and uncalibrated Huff parameters, so new
  lounges look weak and the split is a first cut.
- **Calls move with assumptions.** 12 of 23 lounge calls are low confidence, most within 0.05 of a
  line; 14 lounges flip in some of the 27 drive-time x coverage x worker-share combinations (khaleej-al-arabi most, 16). Affluence weighting is off at baseline.
- **Growth areas are one typical lounge at each area's centre**, judged independently, and the
  6,000 line is a first cut.
- **Midday drive times**, and a competitor search that misses smaller salons where Google's
  20-result cap bites.
