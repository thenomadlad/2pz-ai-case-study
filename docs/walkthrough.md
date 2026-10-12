# Walkthrough

About ten minutes. It follows one question from the Executive Summary to two decisions, shows how the AI
text is made and checked, and ends with where not to trust it. Every number below is what the app
shows at the baseline on 2026-10-11 (15-min drive, 60% competitor coverage, 5.5% women in worker
housing, affluence weighting off). The AI text is paraphrased, not quoted: it is regenerated when the
model changes.

Live app: https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/

## 1. Who it's for and what it decides

**Who decides:** the owner of the network's footprint and capital, on the retail portfolio team. They decide where Bedashing is present and how much capital each site ties up: open, renew, resize, relocate or exit (access to market and deployment of capital). They don't run the branches: service quality, staffing and day-to-day performance belong to operations. So every call answers 'is this a good place to have our capital?', never 'is this branch well run?'

The app answers the two decisions they already make:

- **Lease renewal**, lounge by lounge: **PROTECT** (keep and defend), **HOLD** (no action this
  cycle), **SHRINK** (investigate downsizing or consolidating before the lease event, *not* close).
- **Site search**, for expansion: areas beyond a 15-min drive of every lounge are **GROW** (start a
  site search), **WATCH** (revisit when a named test changes) or **SKIP**.

The rules make every call. Claude only explains them, and every number it writes is checked
against the data.

## 2. The Executive Summary: the answer, then the evidence

Open the [Executive Summary](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/). It opens on
the portfolio team's question, **"Where is my network under pressure, and where should we grow?"**, and answers it in
one sentence: review 3 weak lounge sites, defend 6 strong ones and test 34 areas for new lounges. Of 23
scored lounges, 6 are PROTECT, 14 HOLD and 3 SHRINK; 34 of 561 growth areas are GROW and 63 WATCH. Every
label is judged within the site's emirate against a frozen market of 1,123 competitor salon sites, never
against our own lounges. A warning line says 12 of 23 calls are low confidence and links to *How sure we
are*.

Two collapsed boxes sit under it: **How we measure** (serviceable market per AED of commercial rent,
within each emirate; why rent is the cost signal; why each threshold) and the **AI-written summary**.

Then three cards, each a claim with one number, counted as a share of the ~164k women our lounges serve
today (model estimate): **Review** (3 SHRINK lounges, 7% of our served market), **Grow** (34 areas;
the best, Al Dhaid, would grow it by about 35%) and **Protect** (6 PROTECT lounges, 37%). Each card's
*Evidence ↓* jumps to its section: a map of just those lounges or areas and a table whose names link to
their pages. Growth percentages can't be added up: neighbouring areas reach the same women.

**How sure we are** closes the page: the HOLD band, the low-confidence list, a box of the branch-health
KPIs with what each rests on today and the data that would make us surer, and the **⚠️ Before you trust
these calls** limitations.

**The What-if explorer** is a separate page and the only one that reads a what-if. At the top, the
panel (collapsed at baseline): **Your decision rules** first (weight on demand vs rent, the PROTECT and
SHRINK lines, the GROW minimum and demand line), then the model's assumptions, **Plug in a quote** (a
rent for any lounge or GROW/WATCH area) and **Test a SHRINK** (close lounges). Once anything differs
from the baseline, a **scenario summary** appears under it: Baseline | This scenario | Change for the
lounge calls, low-confidence calls, GROW/WATCH/SKIP counts, the women our lounges serve and their share
in PROTECT and SHRINK lounges, and the best GROW area's growth; then **What changed**, each moved call
as ~~old~~ → **new** with the signal that moved it. Then the full map. Every area is coloured: GROW blue, already captured green (our lounges serve 2%+ of
its women), WATCH purple, SKIP or no data grey; lounges are pins in their call's colour, hollow when low
confidence. *Jump to* pills re-centre on a city, and the legend is a collapsed section under the map.

A scenario in the portfolio team's own levers (numbers from the app):

- **A landlord quote for City Walk.** City Walk is SHRINK at AED 4,561/m² (composite 0.15: demand
  0.30, rent 0.00). Pick it under *Plug in a quote*, enter **2,200** and add it: the summary shows
  SHRINK 3 → 2, HOLD 14 → 15, and *What changed* reads **City Walk at AED 2,200/m² (quote)**:
  ~~SHRINK~~ → **HOLD** (site rent score 0.00 → 0.45). It is a weak HOLD (composite 0.37, low
  confidence): the line sits at about AED 2,290 (2,300 is SHRINK again), barely above Dubai's median
  salon-site rent of 2,154. A renegotiation has to land near the market median to keep the site.
- **Tightening the GROW minimum to 10,000 net new women.** Add it under *Your decision rules*: GROW
  34 → 16, WATCH 63 → 47, SKIP 464 → 498; 18 areas drop ~~GROW~~ → **WATCH**, each listed with the
  women it would add. The best growth area (+35%) is unchanged: the bar only removes the marginal ones.
- **Weighting demand at 70%** moves six calls (Baniyas, Shahama and Shakhbout City to PROTECT; Al Jada
  and West Yas off SHRINK; Khaleej Al Arabi to SHRINK): how much those six hang on the equal weighting.

**Reset to baseline** clears the assumptions, rules and quotes together.

## 3. One lounge decision: city-walk (SHRINK)

Click **City Walk** in the Review evidence table, select its row on the **Lounges** page, or open
[`/lounge?lounge=city-walk`](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/lounge?lounge=city-walk).

**What.** City Walk, Al Wasl, Dubai. *Composite 0.15 · confidence high · the call changes in 0 of 27
assumption combinations.* A typical lounge at its site would serve about **1,900 women** in the Huff
split: **bottom 30% of Dubai salon sites on demand** (the demand score is that percentile, 0.30),
26th percentile UAE-wide. Its shop rent, AED 4,561/m² (its DLD area's median), gives a **rent ratio
of 0.47**: Dubai's median salon site pays under half that. That is below the rent scale's P10 (0.62),
so the rent score is 0; it is the 98th percentile of rent UAE-wide. The page also says *The model
estimates this lounge is performing 1.1x compared to its site*: context, not scored.

**The two signals.** *The two signals, on fixed scales* shows each value, its scale, the UAE-wide
percentile beside it and why the scale is set there: both rank the site within its emirate against a
frozen reference of competitor salon sites (582 in Dubai), never against our own lounges. Right under
it, **What would change the call** is a tree: the call, then each signal, then what drives it, shaded
red (pulls the call down) to green (up). For city-walk the rent rows are deep red. Below the tree:
how the estimates move with each assumption (drive time, competitor coverage, worker housing), the
competitors table and the shared catchment.

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
Overlap alone doesn't make a SHRINK. So the portfolio team's lease-review list starts with city-walk, with
finance's P&L for it before anyone says "close".

## 4. One growth opportunity: Kalba (GROW)

Select Kalba on the **Areas** page (or click its blue cells on the What-if explorer's map), or open
[`/area?area=kalba-sharjah`](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/area?area=kalba-sharjah).

**How this call was made.** Every area is a what-if: open a typical lounge (the median lounge's
reviews and rating) at its centre. In Kalba it would add about **12,500 net new women** (6,000
needed), worker housing is 1% (under 50%), it is in the **top 10% of Sharjah salon sites on demand**
(0.5 needed; 98th percentile UAE-wide), and its rent test is **neutral**: it passes, but the call is
**low confidence**. Premium reviews per 1k women is shown as context.
The caveats: Kalba has no shop rent of its own, so it carries Sharjah's emirate median, which equals
the median at Sharjah's reference salon sites. Where an area's rent is mostly that fallback, the rent
test is scored neutral and the call marked low confidence, as for most of Sharjah's 10 GROW areas. A site far from any salon also tops the demand percentile easily (the
reference sites all have a competitor next door). Distance is a straight line, and Bedashing's only
Sharjah lounges (al-jada, zawaya-walk) are on the Dubai side, which is a business question the model
can't answer.

For a WATCH, compare
[`/area?area=bani-yas-abu-dhabi`](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/area?area=bani-yas-abu-dhabi):
about 8,300 net new women and the top 2% of Abu Dhabi salon sites on demand, but a rent ratio of
0.70, dearer than the median Abu Dhabi salon site (62nd percentile of rent UAE-wide). All 15 WATCH
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
`verify` again and caches only grounded answers. `just explain` (`python -m src.explain api`) is the
only API route (needs a key); any other argument just prints the usage.
Every AI text in the app is captioned *"AI-written (cached): every number in it was checked against
the data."*

**Fallback.** The cache is keyed by a hash of the exact numbers. Change them and the cached text no
longer applies, so a deterministic template takes over. Try it on the **What-if explorer**: set **Drive
time** to **20 min (high)**, or close a lounge under **Test a SHRINK**, then click a lounge on the map.
A *What-if view* banner appears, and where the numbers changed the panel's text is captioned
*"Template — numbers changed by the what-if, so the cached AI text no longer applies."* **Reset to
baseline** brings the AI text back. The other pages always show the baseline, so they keep the AI text.
SKIP areas and the NOT SCORED airport lounge always use the template.

## 6. Where not to trust it

These matter more than the calls. The full ranked list is the app's **README** page
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
- **Services sold are measured by lifetime Google reviews** (our proxy until bookings data) and
  the Huff parameters are uncalibrated, so new lounges look weak and the split is a first cut.
- **Calls move with assumptions.** 12 of 23 lounge calls are low confidence, most within 0.05 of a
  line; 14 lounges flip in some of the 27 drive-time x coverage x worker-share combinations (khaleej-al-arabi most, 16). Affluence weighting is off at baseline.
- **Growth areas are one typical lounge at each area's centre**, judged independently, and the
  6,000 line is a first cut.
- **Midday drive times**, and a competitor search that misses smaller salons where Google's
  20-result cap bites.
