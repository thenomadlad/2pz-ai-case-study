# Limitations of the v3 model

The model is a first pass, and we expect to iterate on it. **Read this before trusting any call.**
The calls (PROTECT / HOLD / SHRINK for lounges, GROW / WATCH / SKIP for areas) are a shortlist
to test with the business, not decisions. Each limitation below says three things: which way it
biases the result, which calls it touches, and what would fix it. They are ordered by how much
they could change what the model says.

Data sources and their own caveats: `data/seed/v3/SOURCES.md`. The notebooks show every step:
`market_size`, `catchments`, `competitors`, `served_demand`, `rent`, `scorecard`, `growth`, and in
`features/`: `affluence`, `features`, `decisions` and `explanations`.

## 1. No revenue or lease data in the model

The lounge scorecard has two signals, both on the site: **site served** (the women a typical lounge
would serve there in a Huff split) and **site cost efficiency** (`cost_index`: site-served women per
AED 1,000 of annual site cost, against one frozen UAE-wide anchor). Site cost is built, not observed: shop rent x an **assumed** 150 m² unit,
plus an **assumed** fit-out of AED 3,000/m² written off over 5 years. There is no revenue, no actual
lease (rent, floor area, terms), no actual capex, no staffing and no footfall. SHRINK means "serves
few women for what its site costs, investigate", not "loses money". A lounge can be SHRINK and
profitable (a cheap lease, loyal clients), and PROTECT and unprofitable.

- **Touches:** every lounge call, and every growth area's cost check.
- **Fix:** per-lounge revenue and the actual leases, even banded. With those, the scorecard becomes a
  return-on-capital view, and the market signals explain *why* a lounge earns what it does.

## 2. Served demand leans on lifetime Google reviews

Each premium supplier's pull in the Huff split (our lounges and premium salons alike) is its Google
review count, times a rating factor ((rating / 4.6)^5) and a drive-time decay (10 / 15 / 20 min:
1 / 0.5 / 0.25). Google review counts are **lifetime totals**, so:

- Older salons look bigger. New lounges (noya-plaza, 215 reviews) serve fewer women in the model
  partly because they are new.
- Chains probably push for reviews more than independents, which may inflate Bedashing.
- Reviews are a proxy for customers, not a count of them.
- **Tourist and visitor skew.** Salons in malls and tourist areas collect reviews from visitors
  who don't live nearby, so they pull harder in the split than their resident trade justifies, and a
  mall-heavy area's premium reviews per 1k women (saturation, see 8) reads high. Incentivised reviews
  push the same way, unevenly.
- **The Huff parameters are a first cut** (2026-10-11): review exponent 1, the decay steps, the rating
  elasticity and the outside option (the median supplier's pull) are starting points, not calibrated
  on where customers actually come from.

The scored demand gives every lounge the median lounge's reviews and rating, so its own review count
moves only its served women and performance vs site (context, not scored).

Capture (the lounge's share of its premium substitutes' reviews) and the rating gap are still
computed and shown on the lounge page, but they are **not scored**: served demand already uses both
reviews and rating.

- **Touches:** the demand signal (half the composite), the cost index (its numerator) and every
  growth area's net new women.
- **Fix:** a better share-of-customers measure: booking-platform data, card-spend panels, or
  footfall (e.g. mobile location data); a customer postcode sample to calibrate the Huff decay.

## 3. Shop rent comes from different sources per emirate

The cost index needs a shop rent (AED/m²/yr) for every lounge and area. Since 2026-10-11 every cell
has one, from the best source its emirate offers:

- **Dubai: DLD Ejari shop contracts** (registered 2026-07-10 to 2026-10-09), the per-area median.
  Signed rents, but an area median mixes street shops with mall units, so a mall lounge's real rent
  can sit well above it (Downtown reads AED 4,561/m²; sanity check SC7).
- **Abu Dhabi: ADREC 2025 street-retail and community-mall rates per district**, matched to the
  cell's OSM name. ADREC's map data service refuses queries (HTTP 403; the API needs a subscription),
  so **the values were read by hand off its public map UI** (`adrec_retail_rent_2025.csv`,
  2026-10-11). A district rate, not a lease, and hand-copied.
- **Northern emirates: Property Finder and Bayut asking rents**, scraped 2026-10-11 through
  third-party Apify actors. **Scraping those portals is a grey area under their terms of service**;
  the owner accepted it and we disclose it. Asking rents run above achieved rents, and Bayut was
  budget-capped to its first ~200-250 results per search.
- **Everywhere else: the emirate median** of the cells that have a rent. That covers a third to a half of
  Dubai's and Abu Dhabi's cells and most of Fujairah's and Ras Al Khaimah's, so many sites in those
  emirates carry their emirate's figure, not their own.
- The JLL mall-class bands used before 2026-10-11 are dropped.

The index compares every site with **one UAE-wide anchor**, frozen at baseline (`COST_ANCHOR` =
14.34 site-served women per AED 1k, the median over the 23 scored lounges), so it never moves when a
lounge opens, closes or grows. The old emirate-median baseline did, and left al-taif-mall (Fujairah)
with no index; it now has one (3.86). The cost: a Dubai contract rent is compared directly with a
northern-emirates asking rent, and **dear Dubai sites score low on cost** (four of the five Dubai
lounges are SHRINK, mirdif-35 HOLD). The anchor must be re-frozen if the served model or site cost
changes.

- **Touches:** the cost signal (half the composite) and the growth cost check.
- **Fix:** the actual leases; ADREC data through its API; contract (not asking) rents in the north.

## 4. The calls depend on the assumptions

The model has four assumption levels: travel time (10/15/20 min), competitor coverage (50/60/70%),
worker-housing female share (1%/5.5%/15%) and affluence elasticity (0/0.5/1). **Affluence is off at
baseline** (elasticity 0: every woman counts the same; why in `notebooks/features/affluence.ipynb`); it
stays only as a what-if axis. Served demand depends on the worker-housing and affluence levels; travel
time sets the catchments shown and which cells are growth areas.

- A lounge is **low confidence** when its composite is within 0.05 of a line, its call changes in a
  third or more (27+) of the 81 level combinations, or it changes when one signal weight moves ±25%.
  At baseline, 7 of 23 are low (2026-10-11); most calls don't change in any combination.
- The app's what-if panel switches the levels, so you can watch a lounge move.
- **Fix:** evidence on how far UAE women actually travel to a salon (a customer postcode sample
  from Bedashing's bookings would settle it).

## 5. Drive times are midday

Reach comes from Mapbox drive-time isochrones at **typical weekday-midday traffic**. TomTom 2025 puts
Dubai evening trips ~40% slower, so after-work reach, when salon demand peaks, is smaller. Huff
counts a supplier within 20 minutes of a cell, with a stepped decay (see 2). Cells without their own
isochrones use straight-line distance bands fitted on the cells that have them.

- **Touches:** served demand, shared catchment and the growth areas.
- **Fix:** rush-hour isochrones as a sensitivity (`isochrone_depart_at` 18:00, ~$0 within
  Mapbox's free tier), and a decay calibrated on customer postcodes.

## 6. The market-size estimate is coarse

Women 15+ per ~2 km cell come from WorldPop adults. WorldPop's sex split is one national ratio
(33.6% female everywhere), so we rebalance: worker housing (OSM industrial land) gets 5.5% women,
calibrated on Dubai labour-camp communities. Against 21 measured Dubai communities, this cuts the
error from 0.21 to 0.13.

- Camps not mapped as industrial in OSM are missed: Dubai Investment Park, Ras Al Khor Industrial
  and very likely Sonapur. **Mirdif-35's market is overstated.**
- There's no income, nationality or age mix. A premium lounge's real market is a slice of these
  women, and with affluence off nothing weights them (see 4).
- Cell membership is decided by the cell's centre point, on a ~2 km grid.
- **WorldPop is a modelled surface, not a count.** The 2025 release (R2025A, constrained) spreads
  census-based totals, projected forward, onto 100 m built-up pixels with a dasymetric model driven
  by covariates such as building footprints. Totals over big areas are anchored; a single ~2 km
  cell is the model's allocation, so a small cell's women can be off by a lot (a new tower block
  missing, or a district's people spread evenly across it). Trust areas and catchments more than any
  one cell. Its age is the release year: neighbourhoods built since aren't in it.
- **Fix:** Dubai/Abu Dhabi statistics-centre community data with the sex split (where published),
  and income or card-spend data UAE-wide.

## 7. The competitor search misses salons

Competitors come from Google Places nearby searches on 1.8 km circles. Each search returns at most
20 salons, ranked by popularity.

- Where circles hit the cap (5% of circles around al-dhafra, 77% around zawaya-walk), smaller
  salons are missed. The correction (`search_recall` 0.66) comes from **one** fully swept tile
  (Al Barsha) and is an upper bound.
- Cells never searched get imputed stand-in competitors from comparable searched cells in the same
  emirate and density tier, so their competition is an estimate.
- "Premium" is mostly a stand-in. Only ~36% of salons have a Google price, so unpriced salons count
  as premium when they have at least the median reviews and a 4.3+ rating. Bedashing's own price
  level is assumed to be `expensive`.
- Home-service salons are invisible. Budget salons and the long tail are left out on purpose:
  the Huff split is over the premium end, not the whole market.
- **Fix:** a full sweep of the capped circles (~1,600-6,000 calls; free from 1 November, ~$54-210
  now; declined 2026-10-09), and Bedashing's real price level from its booking pages.

## 8. Growth areas are a first cut

Growth areas are populated cells beyond a 15-min drive of every scored lounge, one area per OSM place
name (and emirate), whether its cells touch or not. Each is a **what-if: open a typical lounge** (the
median lounge's reviews and rating) at the area's centre and count the women it would add to the
network, net of what it takes from our own lounges. GROW needs 6,000+ net new women, worker housing
under 50%, and cost efficiency at least the UAE-wide anchor (or unknown); WATCH is big but
dearer, big but mostly worker housing, or 3,000+ net new women; SKIP otherwise, or under 5,000 women,
or a non-residential name. Saturation (premium reviews per 1k women) is shown as context, not tested.

- **One site per area, at its centre.** A big or scattered area may hold more than one site, or none
  at its centre. Areas are judged **independently**, so two GROW areas near each other could
  cannibalise each other.
- **Unnamed cells make no growth area.** 67 populated cells outside every catchment (about 34k
  women, 30 of the cells in Dubai) have no OSM admin boundary or place within 3 km, so their only
  name is their emirate's. They stay in catchments, overlap and population totals, but are not
  offered as growth areas.
- **Merging by name can add up scattered pieces.** Same-named cells that don't touch count as one
  area (Habshan's 21 cells span ~39 km; the "Sharjah" area's 53 span ~33 km). The area page's cell
  map shows the spread.
- **Competitor data is partial.** Cells outside the catchments were searched only where they hold
  2,000+ women; the rest use imputed competitors (see 7). Areas with under 50% of their women
  searched are low confidence.
- **Non-residential places are skipped by name.** WorldPop puts people in industrial zones, free
  zones, military bases, airports and ports; areas with such names are SKIP before any test. Camps
  without such a name get through on their worker share alone (Dubai Investments Park is mixed-use
  and stays in; WATCH there means "revisit", not "open").
- **The cost check uses northern-emirates asking rents and many emirate medians** (see 3), and the
  6,000 line is a first cut (about what our median lounge serves today).
- **Many GROW areas are in Sharjah emirate**, beyond a 15-minute drive of Bedashing's two Sharjah
  lounges (al-jada, zawaya-walk), both on the Dubai side. The business question is why the Sharjah
  footprint is only two lounges. The model can't see licensing, brand fit, landlord terms or
  customer mix.
- Distance to the nearest lounge is a straight line, not a drive.
- **Fix:** competitor searches for the remaining cells (~2,000 calls), candidate sites inside each
  area instead of its centre, and a business view on why Sharjah has only two lounges.

## 9. The rating enters only through the Huff pull

Google ratings come in 0.1★ steps, and lounges span only 4.4-4.9★. The rating gap (lounge minus the
median rating of the premium salons in its catchment with 20+ reviews) is shown, not scored. Rating
moves served demand through the Huff attractiveness ((rating / 4.6)^5: 4.8★ ~1.24x, 4.3★ ~0.71x), an
uncalibrated elasticity.

## 10. The scorecard's anchors were calibrated on the data they score

The fixed scales (0 → 20k site-served women, 0.5 → 1.5 cost index around the frozen anchor, and the
PROTECT/SHRINK lines at 0.65/0.35) are a quick first cut (2026-10-11) from these 23 lounges at
baseline levels. They are
judgement, not benchmarks. A different, equally defensible anchor moves lounges near the lines.
That is why the low-confidence flag exists.

## 11. Cannibalisation is shown, not scored

`shared_share` is the share of a lounge's catchment women that another scored lounge also reaches;
`absorbed_share` is the share of its served women siblings would take over if it closed
(leave-one-out). Both are shown on the lounge page and neither is scored: served demand already
splits shared cells between the lounges that reach them. Closing a lounge in the what-if panel
re-runs the split, so its neighbours serve more, by construction. Abu Dhabi city lounges mostly
share 82-100% of their women.

## 12. Excluded and special cases

- **zayed-international-airport** is NOT SCORED: it serves travellers, not the women around it. It
  stays on the map but is left out of every comparison: it is no lounge's sibling in the shared
  catchment, no lounge's premium substitute, no area's nearest lounge, and its catchment cells are
  open to growth areas. **This was a bug until 2026-10-10:** the airport counted as a sibling and as
  a premium substitute. The sanity checks caught it, not the model's own tests.
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
ADREC rates (2025) were read off its map and the shop listings scraped on 2026-10-11; GHSL built
form is 2018.

## 15. Site cost is assumed around a real rent

- **The 150 m² unit and the fit-out are assumptions.** Lounge floor areas aren't public; the fit-out
  (AED 3,000/m², 5 years) is not sourced. Fit-out is the same per site, so it narrows the cost gap
  between dear and cheap sites.
- **Rent is not a pure cost.** Shop rent also tracks footfall and affluence, i.e. revenue. The cost
  index marks down prime sites, and without revenue (see 1) the model can't tell whether the
  footfall pays for the rent.
- **Rents are medians, rates or asking rents** (see 3), not the lounge's lease.
- **Fix:** the actual leases (rent and floor area per lounge) and fit-out costs.

## How this compares with standard retail-location methods

| Method | What it does | What we do instead, and the gap |
|---|---|---|
| **Huff gravity** | Each customer's patronage split across stores by attractiveness ÷ distance^λ | **Implemented, uncalibrated.** Each cell's women split across the premium suppliers within 20 min (reviews x rating factor x stepped drive-time decay) plus an outside option. The decay and exponents are starting points, not fitted on customer origins (see 2) |
| **Voronoi / nearest-facility** | Each customer goes to the nearest store; trade areas never overlap | We use **drive-time isochrones**, which overlap, and the Huff split shares an overlapping cell between the suppliers that reach it. `shared_share` still shows the raw overlap (see 11) |
| **Index of Retail Saturation** | Demand × spend ÷ supply | The growth areas' **premium reviews per 1k women** is an IRS-like supply ÷ demand ratio, inverted, with **no spend term**. It is shown as context, not tested |
| **MCDA / weighted overlay** | Score sites on several criteria with stated weights | The lounge scorecard **is** one: two signals on fixed anchors, equal weights. The anchors and weights are judgement (see 10); the confidence flag tests the four assumption levels and each weight ±25%, not the anchors |
| **MCLP / location-allocation** | Pick the *set* of new sites that maximises coverage together | We score each growth area **independently** with a one-site what-if, so two GROW areas near each other could cannibalise each other, and a big area may hold more than one site (see 8) |
| **Analog / sales regression** | Predict a site's sales from comparable stores' revenue | Needs per-lounge revenue, which we don't have. **This is the main reason the scorecard is a proxy** (see 1) |
