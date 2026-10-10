# Limitations of the v3 model

The model is a first pass, and we expect to iterate on it. **Read this before trusting any call.**
The calls (PROTECT / HOLD / SHRINK for lounges, GROW / WATCH / SKIP for areas) are a shortlist
to test with the business, not decisions. Each limitation below says three things: which way it
biases the result, which calls it touches, and what would fix it. They are ordered by how much
they could change what the model says.

Data sources and their own caveats: `data/seed/v3/SOURCES.md`. The notebooks show every step:
`market_size`, `catchments`, `competitors`, `affluence`, `features`, `decisions` and `explanations`.

## 1. No money in the model

There is no revenue, rent, capex, staffing or lease data. The model scores **location and market
position** only. SHRINK means "weak on most market signals, investigate", not "loses money". A
lounge can be SHRINK and profitable (low rent, loyal clients), and PROTECT and unprofitable.

- **Touches:** every lounge call.
- **Fix:** per-lounge revenue and rent, even banded. With those, the scorecard becomes a
  return-on-capital view, and the market signals explain *why* a lounge earns what it does.

## 2. Capture is measured with lifetime Google reviews

Capture = the lounge's reviews ÷ (its own reviews + its premium substitutes' reviews). Google
review counts are **lifetime totals**, so:

- Older salons look bigger. New lounges (noya-plaza, 215 reviews) look weak partly because they
  are new.
- Chains probably push for reviews more than independents, which may inflate Bedashing.
- Reviews are a proxy for customers, not a count of them.
- **Tourist and visitor skew.** Salons in malls and tourist areas collect reviews from visitors
  who don't live in the catchment. That inflates their review counts against the catchment's
  resident women: a mall lounge's capture, and a mall-heavy area's premium reviews per 1k women
  (saturation, see 8), both read high. Incentivised reviews push the same way, unevenly.

Capture also falls as competition rises. Across lounges, catchment women and capture have a
Spearman correlation of **−0.74**: big Dubai markets are crowded, so the lounge's share there is
tiny (about 1%, 0.8-1.6%, at al-barsha, city-walk, jumeirah-park and nad-al-sheba). Demand and capture
partly cancel, and a big crowded market tends to land in HOLD. We considered replacing both with
one "estimated customers" signal and rejected it, because, when tested on 2026-10-09, it turned four of the
five Dubai lounges into SHRINK (`decisions.ipynb`, open question a). Rejecting a signal for its
outcome is the tuning-to-taste the rubric warns about (MO7), so we name it here.

- Capture is a **proxy of a proxy**: reviews stand in for customers, and customers stand in for
  share of the premium market.
- **Touches:** the capture signal (1 of 3.5 weight), and so every composite.
- **Fix:** a better share-of-customers measure: booking-platform data, card-spend panels, or
  footfall (e.g. mobile location data). A Huff gravity model (each woman's spend split across
  salons by attractiveness ÷ distance) would replace both catchments and capture.

## 3. Affluence is observed in Dubai only

Demand counts **addressable women**: each cell's women weighted by how its median household rent
compares with the women-weighted median (`(rent / median) ^ elasticity`, clipped to 0.25-4 before
rescaling to a mean of 1 over the observed cells; final weights 0.44-2.53 at medium, 0.18-2.68 at
strong).
The rents are DLD Ejari contracts for one flat, villa or studio, registered 2026-07-10 to
2026-10-09 (`affluence.ipynb`). This is the only affluence signal in the model, and it is thin:

- **Dubai only.** 241 Dubai cells have an observed rent (81% of Dubai's women); the other 2,132
  cells, 73% of the UAE's women, are weighted **neutral** (1). Every Abu Dhabi, Sharjah, Fujairah
  and RAK lounge, and every growth area outside Dubai, gets no affluence adjustment. So any
  Dubai-vs-elsewhere comparison mixes weighted and unweighted demand. Within Dubai the weights move
  women from cheap cells to dear ones (al-barsha +18% addressable, mirdif-35 −4%).
- **The UAE-wide proxy failed.** 2018 built form (GHSL: villa share, towers, greenery, height)
  does not predict Dubai rents: cross-validated R² **−0.10**, villa share's Spearman correlation
  0.01, the best feature 0.20. So nothing is predicted outside Dubai.
- **Rent is not income, and not salon spend.** It is a household's housing cost; families who
  share a villa, and company-paid housing, blur it.
- **Three months of registrations.** DLD's open-data site serves at most 3 months and sits behind
  a captcha, so the CSV was downloaded by hand. New and renewed contracts only.
- **Area medians hide people.** A cell's rent is the median of the DLD areas whose point falls in
  it (else the nearest within 2.5 km): a rich woman in a cheap cell is invisible. Only **102 of the
  241** cells contain a DLD area point; the other **139 borrow the nearest area's rent**
  (`assignment` in `cell_affluence.csv`).
- **Name matching.** DLD land-registry names were matched to OSM names: 168 of 173 areas (99% of
  contracts) located, 7 of them by a hand-written alias (Marsa Dubai, Burj Khalifa, Palm Jumeirah…).
- **The elasticity is an assumption** (off 0 / medium 0.5 / strong 1). No data ties salon spend to
  rent.
- **Touches:** demand for the five Dubai lounges and zawaya-walk (3% observed), and the size test
  of the 43 growth areas with any observed rent, all in Dubai. **No call changes** at any
  elasticity: the four big Dubai lounges sit above the 200k demand anchor weighted or not, and
  jumeirah-park and zawaya-walk move by under 0.02. **al-awir-dubai** (19.4k women, 20.1k
  addressable at medium) passes the size line only through the weighting, on one DLD area (Al
  Aweer First, 65 villa-heavy contracts) covering 38% of its women; the growth rule caps such an
  area at WATCH.
- **Bias: Dubai lounges look better than the rest.** The weights average 1 within Dubai's
  observed cells, so affluence only reshuffles demand between Dubai cells; it can't say whether
  Dubai is richer than Abu Dhabi. Dubai lounges in above-average-rent catchments gain (al-barsha
  +18%), while an equally affluent Abu Dhabi catchment stays at 1, so Dubai lounges are inflated
  relative to non-Dubai ones. All 5 SHRINKs are in Abu Dhabi, the part affluence can't see. The
  near-zero effect on the calls is partly this design, not evidence that affluence doesn't matter.
- **Fix:** Abu Dhabi rents from ADREC (its public map's data service refuses queries, HTTP 403;
  the API needs a subscription); the Sharjah rental index when it is published; per-cell income or
  card-spend data, which would replace rent altogether.

## 4. The calls depend on the assumptions

The model has four assumption levels: travel time (10/15/20 min), competitor coverage
(50/60/70%), worker-housing female share (1%/5.5%/15%) and affluence elasticity (0/0.5/1). Travel time matters most: 20 min
roughly doubles most catchments compared with 15 (median ×1.86), and 10 min shrinks them to about
a third.

- **10 of 23** scored lounges are **low confidence**: within 0.05 of a threshold, missing an input,
  a thin market, a call that changes in a third or more (27+) of the 81 level combinations, or one
  that changes when a single signal weight moves ±25% (in practice that only catches calls already
  within 0.05 of a line). mohammed-bin-zayed-city flips in 54 of 81, and al-barsha and city-walk
  in 27. al-maqta flips in only 9, but it is low confidence anyway: it is HOLD by 0.003. The affluence level moves no lounge on its own, so these are three times the
  counts over the other three levels.
- The app's what-if panel switches the levels, so you can watch a lounge move.
- **Fix:** evidence on how far UAE women actually travel to a salon (a customer postcode sample
  from Bedashing's bookings would settle it).

## 5. Drive times are midday, with no distance decay

Catchments are Mapbox drive-time polygons at **typical weekday-midday traffic**. TomTom 2025 puts
Dubai evening trips ~40% slower, so after-work catchments, when salon demand peaks, are smaller.
Inside the polygon every woman counts fully. Outside it, nobody counts. Mall lounges probably draw
from further away.

- **Touches:** demand, cannibalisation and the growth areas.
- **Fix:** rush-hour isochrones as a sensitivity (`isochrone_depart_at` 18:00, ~$0 within
  Mapbox's free tier), then distance decay (Huff).

## 6. The market-size estimate is coarse

Women 15+ per ~2 km cell come from WorldPop adults. WorldPop's sex split is one national ratio
(33.6% female everywhere), so we rebalance: worker housing (OSM industrial land) gets 5.5% women,
calibrated on Dubai labour-camp communities. Against 21 measured Dubai communities, this cuts the
error from 0.21 to 0.13.

- Camps not mapped as industrial in OSM are missed: Dubai Investment Park, Ras Al Khor Industrial
  and very likely Sonapur. **Mirdif-35's market is overstated.**
- There's no income, nationality or age mix. A premium lounge's real market is a slice of these
  women; observed Dubai rents weight them, and nothing else does (see 3).
- Cell membership is decided by the cell's centre point, on a ~2 km grid.
- **WorldPop is a modelled surface, not a count.** The 2025 release (R2025A, constrained) spreads
  census-based totals, projected forward, onto 100 m built-up pixels with a dasymetric model driven
  by covariates such as building footprints. Totals over big areas are anchored; a single ~2 km
  cell is the model's allocation, so a small cell's women can be off by a lot (a new tower block
  missing, or a district's people spread evenly across it). Trust areas and catchments more than any
  one cell. Its age is the release year: neighbourhoods built since aren't in it.
- **Fix:** Dubai/Abu Dhabi statistics-centre community data with the sex split (where published),
  and affluence data outside Dubai (see 3).

## 7. The competitor search misses salons

Competitors come from Google Places nearby searches on 1.8 km circles. Each search returns at most
20 salons, ranked by popularity.

- Where circles hit the cap (5% of circles around al-dhafra, 77% around zawaya-walk), smaller
  salons are missed. The correction (`search_recall` 0.66) comes from **one** fully swept tile
  (Al Barsha) and is an upper bound.
- "Premium" is mostly a stand-in. Only ~36% of salons have a Google price, so unpriced salons count
  as premium when they have at least the median reviews and a 4.3+ rating. Bedashing's own price
  level is assumed to be `expensive`.
- Home-service salons are invisible. Budget salons and the long tail are left out on purpose:
  capture is a share of the premium end, not of the whole market.
- **Thin markets:** al-dhafra (7 premium salons) and al-falah (6) have under 10, so their capture
  score is pulled toward neutral (0.5) in proportion: with n salons it keeps n/10 of its distance from
  0.5, a blend rather than a cliff. Their calls are low confidence.
- **Fix:** a full sweep of the capped circles (~1,600-6,000 calls; free from 1 November, ~$54-210
  now; declined 2026-10-09), and Bedashing's real price level from its booking pages.

## 8. Growth areas are a first cut

Growth areas are populated cells beyond a 15-min drive of every scored lounge, grouped by OSM place
name and split into contiguous pieces.

- **Competitor data is partial.** Cells outside the catchments were searched only where they hold
  2,000+ women. Areas with under 50% of their women searched are capped at WATCH, and their
  saturation is computed over the searched cells only. 540 of 580 areas are SKIP; most are small.
- **Non-residential places are skipped by name.** WorldPop puts people in industrial zones, free
  zones, military bases, airports and ports; 29 areas with such names are SKIP before any test. Small,
  unsaturated areas that are mostly worker housing are SKIP too. Camps without such a name get through
  on their worker share alone. Dubai Investments Park stays WATCH at 4% worker housing (see 6), and we
  accept that: it is mixed-use, with residential communities alongside the industrial plots, so it is
  not a clear non-residential name. WATCH there means "revisit", not "open".
- **Saturation reads high where visitors review** (malls, tourist strips; see 2): their reviews
  count against resident women only.
- **The saturation line (150 premium reviews per 1k women) is still set from our own lounges.** It
  was 50, which sat below every lounge catchment with a real premium market (88+), so GROW only went to near-empty
  places and would have refused the markets Bedashing already operates in. Back-test BT5
  (`SANITY_CHECKS.md`) found clustering doesn't hurt: premium salons with 3+ neighbours within
  1.5 km have a median of about 220 reviews against 126 for isolated ones. So the line was
  recalibrated by a rule fixed before seeing the result: the 25th percentile of the 21 lounge
  catchments with a real premium market (10+ premium salons; they run 88-630), 152.8, rounded to
  150. The lounges' own catchments are measured the same way and shown on the lounge pages. The
  tilt toward empty areas is reduced, not gone: the line is a quarter of the way up our markets,
  and the five GROW areas run 5-59. It is still judgement, calibrated on the data it judges.
- **Al Awir (Dubai) is a WATCH whose size passes only on thin affluence data** (see 3): 19.4k
  women, 20.1k addressable at medium, against a 20k line, with rents for 38% of its women.
- **4 of the 5 GROW areas are in Sharjah emirate** (Sharjah, Al Dhaid, Khor Fakkan, Kalba); the
  fifth is Al Jerf in Ajman. The Sharjah four are beyond a 15-minute drive of Bedashing's two Sharjah lounges (al-jada, zawaya-walk), both on the Dubai
  side; the "Sharjah" area's centre is ~13 km from al-jada. The business question is why the
  Sharjah footprint is only two lounges. The model can't see licensing, brand fit,
  landlord terms or customer mix. "Sharjah" is one 91k-women area. It's contiguous, so it wasn't
  split, and it may support more than one site.
- Distance to the nearest lounge is a straight line, not a drive.
- **Fix:** competitor searches for the remaining cells (~2,000 calls), drive-time catchments
  around candidate sites, and a business view on why Sharjah has only two lounges.

## 9. The rating signal is weak

Google ratings come in 0.1★ steps, and lounges span only 4.4-4.9★. The rating gap (lounge minus
the median rating of the premium salons in its catchment with 20+ reviews) takes only a handful of values. It counts at **half weight**. Most lounges rate slightly
below those salons (the median gap is −0.1★); we checked, and this is not caused by the
premium filter.

## 10. The scorecard's anchors were calibrated on the data they score

The fixed scales (0 → 200k addressable women, 0 → 15% capture, ±0.3★, and the PROTECT/SHRINK lines at
0.65/0.35) were set on 2026-10-09 from these 23 lounges at medium levels, and reviewed by the
user. They are judgement, not benchmarks. A different, equally defensible anchor moves lounges
near the lines. That is why the low-confidence flag exists.

## 11. Cannibalisation is a symmetric share

`shared_share` is the share of a lounge's catchment women that another scored lounge also reaches. It
penalises both lounges in an overlap equally. It doesn't model where the customers would go if one
closed. Closing a lounge in the what-if panel makes its neighbours look better, by construction.
Abu Dhabi city lounges mostly share 82-100% of their women. SHRINK is
driven by this raw overlap, not by services that would be lost if a lounge closed: the model has
no capacity, no served demand and no ROIC (see 1).

## 12. Excluded and special cases

- **zayed-international-airport** is NOT SCORED: it serves travellers, not the women around it. It
  stays on the map but is left out of every comparison: it is no lounge's sibling in the shared
  catchment, no lounge's premium substitute, no area's nearest lounge, and its catchment cells are
  open to growth areas. **This was a bug until 2026-10-10:** the airport counted as a sibling and as
  a premium substitute, and that was part of why shahama was SHRINK (composite 0.32, 87% shared).
  Removing it from both moved shahama to HOLD (0.38, 82% shared), and shifted al-maqta,
  khalifa-city-a (100% → 97% shared), ministries-complex, noya-plaza and westyas slightly. The
  sanity checks caught it, not the model's own tests.
- **The rating gap used the top-k substitutes' median until 2026-10-10.** k grows with the premium
  pool, so adding a strong competitor could change which salons counted and raise a lounge's score
  (sanity check SC4). The gap now uses the median of the whole premium pool (salons with 20+
  reviews). Fixing it moved al-maqta from SHRINK to HOLD at 0.353, 0.003 above the line: a
  knife-edge call, flagged low confidence.
- **New lounges** (e.g. noya-plaza): see 2. Lifetime reviews understate them.

## 13. The explanations

The AI explanations were written in a Claude Code session from the same prompts the API would get
(`python -m src.explain prompts|check|ingest`), not by the API. The grounding check verifies every
number and cited value against the fact sheet, but not adjectives, and not numbers spelled out as
words. A changed number falls back to the deterministic template. Areas marked SKIP and the airport
always use the template.

## 14. Freshness

Google data was fetched 2026-10-08/09. Google's terms allow storing only `place_id` indefinitely;
the rest should be refreshed within 30 days. WorldPop is the 2025 release; OSM is a 2026-07-28
snapshot. DLD rents are contracts registered 2026-07-10 to 2026-10-09, downloaded 2026-10-10;
GHSL built form is 2018.

## How this compares with standard retail-location methods

| Method | What it does | What we do instead, and the gap |
|---|---|---|
| **Huff gravity** | Each customer's patronage split across stores by attractiveness ÷ distance^λ | **Not implemented.** It needs a λ calibrated on where customers actually come from (booking postcodes we don't have) and travel times from every cell to every salon. We use hard 15-min catchments plus a review share (capture), so there is no distance decay and no probabilistic split (see 2, 5). `cell_isochrones.geojson` is kept for this work |
| **Voronoi / nearest-facility** | Each customer goes to the nearest store; trade areas never overlap | We use **drive-time isochrones**, which do overlap. The overlap is the point: `shared_share` measures exactly what a Voronoi split would hide. Women in an overlap count in full for every lounge that reaches them; `shared_share` flags that but doesn't split them (see 11) |
| **Index of Retail Saturation** | Demand × spend ÷ supply | The growth areas' **premium reviews per 1k women** is an IRS-like supply ÷ demand ratio, inverted, with **no spend term**: reviews stand in for supply capacity, and it divides by raw women. The only nod to spend is the separate size test on addressable (rent-weighted) women, which works in Dubai only (see 3) |
| **MCDA / weighted overlay** | Score sites on several criteria with stated weights | The lounge scorecard **is** one: four signals on fixed anchors, stated weights (1/1/1/½). The anchors and weights are judgement (see 10); the confidence flag tests the four assumption levels and each weight ±25% (which only catches calls already within 0.05 of a line), not the anchors |
| **MCLP / location-allocation** | Pick the *set* of new sites that maximises coverage together | We score each growth area **independently**, so two GROW areas near each other could cannibalise each other, and a big area may hold more than one site (see 8) |
| **Analog / sales regression** | Predict a site's sales from comparable stores' revenue | Needs per-lounge revenue, which we don't have. **This is the main reason the scorecard is a proxy** (see 1) |
