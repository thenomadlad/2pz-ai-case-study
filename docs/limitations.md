# Limitations of the v3 model

The model is a first pass, and we expect to iterate on it. **Read this before trusting any call.**
The calls (PROTECT / HOLD / SHRINK for lounges, GROW / WATCH / SKIP for areas) are a shortlist
to test with the business, not decisions. Each limitation below says three things: which way it
biases the result, which calls it touches, and what would fix it. They are ordered by how much
they could change what the model says.

Data sources and their own caveats: `data/seed/v3/SOURCES.md`. The notebooks show every step:
`branches`, `market_size`, `catchments`, `competitors`, `served_demand`, `rent`, `scorecard`, `growth`, and in
`features/`: `affluence`, `features`, `decisions` and `explanations`.

## 1. No revenue or lease data in the model

The lounge scorecard has two signals, both on the site and both ranked within its emirate's frozen
market of competitor salon sites (`data/seed/v3/site_reference.csv`, see 10): **demand percentile**
(`demand_pct`: the share of those sites a typical lounge here would out-serve in a Huff split) and
**rent ratio** (`rent_ratio`: the emirate's median shop rent at those sites ÷ this site's). Each is
shown with its UAE-wide percentile as context. The only money in the model is the site's shop rent
per m², scored as that rent ratio.
There is no revenue, no actual lease (rent, floor area, terms), no actual capex, no capacity data (service
providers, hours, bookings) and no footfall. SHRINK means "a weak site for its emirate, on demand and rent, investigate", not "loses
money". A lounge can be SHRINK and
profitable (a cheap lease, loyal clients), and PROTECT and unprofitable.

- **Touches:** every lounge call, and every growth area's rent check.
- **Fix:** per-lounge revenue and the actual leases, even banded. With those, the scorecard becomes a
  return-on-capital view, and the market signals explain *why* a lounge earns what it does.

## 2. Services sold are measured by lifetime Google reviews

Google reviews are our proxy for **services sold**: each review is a trace of past appointments, so a
salon's lifetime reviews stand in for how much it has sold. Each premium supplier's weight in the
Huff split (our lounges and premium salons alike) is its reviews, times a rating factor
((rating / 4.6)^5) and a drive-time decay (10 / 15 / 20 min: 1 / 0.5 / 0.25), so a salon's share of
the market follows how much it sells. Google review counts are **lifetime totals**, so:

- Older salons look bigger. New lounges (noya-plaza, 215 reviews) serve fewer women in the model
  partly because they are new.
- Chains probably push for reviews more than independents, which may inflate Bedashing.
- Review rates differ between salons and services, so reviews are a stand-in for services sold
  until bookings data, not a count of them.
- **Tourist and visitor skew.** Salons in malls and tourist areas collect reviews from visitors
  who don't live nearby, so they look like they sell more to residents than they do, and a
  mall-heavy area's premium reviews per 1k women (saturation, see 8) reads high. Incentivised reviews
  push the same way, unevenly.
- **The Huff parameters are a first cut** (2026-10-11): review exponent 1, the decay steps, the rating
  elasticity and the outside option (the median supplier's weight) are starting points, not calibrated
  on where customers actually come from.

The scored demand gives every lounge the same typical lounge (frozen at 757 reviews, 4.6★), so how much it sells itself
moves only its served women and performance vs site (context, not scored).

Capture (the lounge's share of its premium substitutes' reviews) and the rating gap are still
computed and shown on the lounge page, but they are **not scored**: served demand already uses both
reviews and rating.

- **Touches:** the demand signal (half the composite), the frozen salon-site reference it is ranked
  against, and every growth area's net new women and demand test.
- **Fix:** a better share-of-customers measure: booking-platform data, card-spend panels, or
  footfall (e.g. mobile location data); a customer postcode sample to calibrate the Huff decay.

## 3. Shop rent comes from different sources per emirate

The rent ratio needs a shop rent (AED/m²/yr) for every lounge, area and reference salon site. Since 2026-10-11 every cell
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

The rent ratio compares a site only with **its own emirate's reference salon sites** (their median
shop rent), so a Dubai contract rent is never set against a northern asking rent, and expensive Dubai
sites are no longer marked down for being in Dubai (the UAE-wide cost anchor used before 2026-10-11
put four of the five Dubai lounges on SHRINK; now only city-walk is, at its DLD area's AED 4,561/m²,
rent ratio 0.47). The UAE-wide rent percentile is shown beside it as context, not scored. What is
still wrong:

- **An emirate-median rent is no observation, so it no longer decides a call (2026-10-11).** A cell
  with no rent of its own gets the emirate median of the cells that have one; in Sharjah that equals
  the reference median (AED 1,121/m²), so the ratio came out exactly 1.00, and in Ajman 0.997. Where
  half or more of an area's women sit in such cells, its women-weighted median *is* that one number,
  so the GROW rent test is **neutral** (passes) and the call **low confidence**, with a caveat
  (`growth.RENT_FALLBACK_WHY`). A lounge whose site cell is on the fallback (al-ain, al-falah) scores
  rent neutral (0.5), low confidence. Effect: manama-ajman (about 35,000 net new women) and
  mudayrah-ajman move WATCH → GROW; nine Sharjah GROW areas, al-awir, al-sad and four Ras Al
  Khaimah areas stay GROW at low confidence; al-ain and al-falah stay PROTECT at low confidence.
  **Known edge:** sharjah-sharjah is 15% fallback, so it keeps its observed-rent call (GROW, ratio
  1.000), but its median lands on the fallback value; its listings cells alone give 0.997.
- **The reference medians mix sources too**: Dubai's is contract rents, Abu Dhabi's district rates,
  the north's asking rents or emirate medians, so "cheaper than the median salon site" means
  different things per emirate.
- The reference and the rent scale (P10 0.62, P90 1.43) are frozen; rebuild them
  (`scripts/build_site_reference.py`) and say so if the rents change.

- **Touches:** the cost signal (half the composite) and the GROW rent test.
- **Fix:** the actual leases; ADREC data through its API; contract (not asking) rents in the north.

## 4. The calls depend on the assumptions

The model has four assumption levels: travel time (10/15/20 min), competitor coverage (50/60/70%),
worker-housing female share (1%/5.5%/15%) and affluence elasticity (0/0.5/1). **Affluence is off at
baseline** (elasticity 0: every woman counts the same; why in `notebooks/features/affluence.ipynb`); it
is not offered in the app. The other three reach the served-demand (Huff) scoring: travel time sets
the decay across the 10/15/20-min bands (10 min keeps only the nearest band; 20 min flattens it;
reach itself can't go past 20 min), competitor coverage scales every competitor's weight by coverage /
60%, and worker-housing share sets the women. Medium reproduces the baseline; the salon-site reference
stays frozen at baseline, so a level that moves every site's demand moves it against a fixed bar
(`src/model/served.py`, LEVELS_WHY). The confidence check and the app's what-if vary those three.

- A lounge is **low confidence** when its composite is within 0.05 of a line, its call changes in a
  third or more (9+) of the 27 combinations of those three levels, or it changes when one signal weight
  moves ±25%. At baseline, 12 of 23 are low (2026-10-11, after wiring drive time and coverage in);
  jumeirah-park joined (9 of 27), and khaleej-al-arabi flips most (16 of 27).
- The app's what-if panel switches the three levels, so you can watch a lounge move.
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

Growth areas are the populated cells that share an OSM place name (and emirate), one area per name,
whether its cells touch or not; cells an open lounge already reaches stay in (the "Sharjah" area: 62%
of its women are within a 15-min drive of al-jada, zawaya-walk or mirdif-35). Each is a **what-if:
open a typical lounge** (frozen at 757 reviews, 4.6★: the scored lounges' medians at the 2026-10-11
baseline) at the area's centre and count the women it would add to the
network, net of what it takes from our own lounges. GROW needs 6,000+ net new women, worker housing
under 50%, a rent ratio of 1+ (no more expensive than its emirate's median salon site; unknown or the
emirate-median fallback passes) and a
demand percentile of 0.5+ (the what-if lounge would out-serve at least half its emirate's reference
salon sites; UAE-wide for emirates with under 50); WATCH is big but more expensive or with weaker demand, big
but mostly worker housing, or 3,000+ net new women; SKIP otherwise, or under 5,000 women,
or a non-residential name. Saturation (premium reviews per 1k women) is shown as context, not tested.

- **One site per area, at its centre.** A big or scattered area may hold more than one site, or none
  at its centre. Areas are judged **independently**, so two GROW areas near each other could
  cannibalise each other.
- **Unnamed cells make no growth area.** 67 populated cells outside every catchment (about 34k
  women, 30 of the cells in Dubai) have no OSM admin boundary or place within 3 km, so their only
  name is their emirate's. They stay in catchments, overlap and population totals, but are not
  offered as growth areas.
- **Merging by name can add up scattered pieces.** Same-named cells that don't touch count as one
  area (Habshan's 21 cells span ~39 km; the "Sharjah" area's 89 span ~33 km). The area page's cell
  map shows the spread.
- **Competitor data is partial.** Cells outside the catchments were searched only where they hold
  2,000+ women; the rest use imputed competitors (see 7). Areas with under 50% of their women
  searched are low confidence.
- **Non-residential places are skipped by name.** WorldPop puts people in industrial zones, free
  zones, military bases, airports and ports; areas with such names are SKIP before any test. Camps
  without such a name get through on their worker share alone (Dubai Investments Park is mixed-use
  and stays in; WATCH there means "revisit", not "open").
- **The rent check uses northern-emirates asking rents and many emirate medians** (see 3: where the
  emirate median sets an area's rent the test is neutral, so 17 of the 34 GROW areas carry no rent
  test at all), and the 6,000 line is a first cut (about what our
  median lounge serves today).
- **The demand test is easy to pass far from salons.** The reference sites are where competitors
  already trade, each ranked with that competitor still open beside the what-if lounge; an area with
  no salons nearby out-serves most of them by construction (Al Dhaid: top 1% of Sharjah's). Net new
  women stay the real size test; the demand percentile mostly screens out crowded spots.
- **Keep and grow use different bars.** Keep or shrink is judged within the emirate (demand
  percentile among its salon sites); growth needs an absolute 6,000 net new women. So a PROTECT site
  can fail the growth test as a new opening: nad-al-sheba is PROTECT (it out-serves 68% of Dubai
  salon sites), yet a typical lounge there would serve about 2,700 women, under half the floor. Not
  a contradiction (an open lounge's site is already paid for; a new one must earn its fit-out), but
  the two lists are not on one scale.
- **10 of the 34 GROW areas are in Sharjah emirate**, and 9 of them lie beyond a 15-minute drive of
  Bedashing's two Sharjah lounges (al-jada, zawaya-walk), both on the Dubai side. The tenth, the
  "Sharjah" area (Sharjah city), is 2.5 km from al-jada; the two lounges already reach 62% of its
  women. The business question is why the Sharjah footprint is only two lounges. The model can't
  see licensing, brand fit, landlord terms or customer mix.
- Distance to the nearest lounge is a straight line, not a drive.
- **Fix:** competitor searches for the remaining cells (~2,000 calls), candidate sites inside each
  area instead of its centre, and a business view on why Sharjah has only two lounges.

## 9. The rating enters only through the Huff weight

Google ratings come in 0.1★ steps, and lounges span only 4.4-4.9★. The rating gap (lounge minus the
median rating of the premium salons in its catchment with 20+ reviews) is shown, not scored. Rating
moves served demand through the Huff attractiveness ((rating / 4.6)^5: 4.8★ ~1.24x, 4.3★ ~0.71x), an
uncalibrated elasticity.

## 10. The scorecard is judged against a frozen market of competitor salon sites

Since 2026-10-11 both signals rank a site within its emirate against a **frozen reference of 1,123
real premium competitor salon sites** (no imputed competitors, no Bedashing; built once by
`scripts/build_site_reference.py`): Dubai 582, Abu Dhabi 304, Sharjah 143, Ajman 38, Ras Al Khaimah
33, Fujairah 18, Umm Al Quwain 5. Per site: its cell's shop rent and the women a typical lounge (757
reviews, 4.6★) would serve there with all our lounges open. That typical lounge is **frozen** at those
baseline medians (`lounges.TYPICAL_WHY`) for every what-if too: a live median drifted when a lounge
closed (khaleej-al-arabi 0.3504 → 0.3488 with nothing of its own changed). Our own lounges are never in it, and
nothing we open or close moves it. This replaced scales calibrated on our 23 lounges (0 → 20k
site-served women, and a cost index against one UAE-wide anchor), which judged the network against
itself.

- **Demand** = the site's empirical percentile among its emirate's reference sites; the 0..1
  percentile is the score. Emirates with under 50 reference sites (Ajman, Ras Al Khaimah, Fujairah,
  Umm Al Quwain) are ranked UAE-wide: a percentile among 5-38 sites jumps several points per site.
  So al-taif-mall (Fujairah) and ras-al-khaimah are ranked against Dubai and Abu Dhabi sites.
- **Rent** = the emirate's median reference rent ÷ the site's, on a frozen P10-P90 scale (0.62 → 0,
  1.43 → 1; the median site, ratio 1, scores about 0.47).
- **Still judgement.** Who counts as a reference site (premium competitors only), the 50-site floor,
  the P10-P90 rent scale and the PROTECT/SHRINK lines at 0.65/0.35 are choices, not benchmarks. The
  reference inherits every served-demand weakness (see 2) and every rent-source mix (see 3), and a
  "typical lounge at a competitor's door" is not a typical lounge site. A different, equally
  defensible choice moves lounges near the lines; that is why the low-confidence flag exists.
- **The UAE-wide percentiles are context only**: a top-quartile Fujairah site can be a middling one
  UAE-wide, and the page says so ("top 10% of UAE salon sites (Fujairah has under 50) on demand ·
  90th percentile UAE-wide").

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

## 15. Site cost is a shop rent per m², not the lease

Site cost should be the real rent for the space a lounge needs to serve its catchment; the model only
has a shop rent per m² (see 3), and that rent per m², against its emirate's median salon site, is the
only cost it scores. No floor area, fit-out or lease terms enter any call (lounge floor areas aren't
public).
- **Rent is not a pure cost.** Shop rent also tracks footfall and affluence, i.e. revenue. The rent
  ratio marks down prime sites within their emirate, and without revenue (see 1) the model can't tell whether the
  footfall pays for the rent.
- **Rents are medians, rates or asking rents** (see 3), not the lounge's lease.
- **Fix:** the actual leases (rent and floor area per lounge) and fit-out costs.

## How this compares with standard retail-location methods

| Method | What it does | What we do instead, and the gap |
|---|---|---|
| **Huff gravity** | Each customer's patronage split across stores by attractiveness ÷ distance^λ | **Implemented, uncalibrated.** Each cell's women split across the premium suppliers within 20 min (reviews x rating factor x stepped drive-time decay) plus an outside option. The decay and exponents are starting points, not fitted on customer origins (see 2) |
| **Voronoi / nearest-facility** | Each customer goes to the nearest store; trade areas never overlap | We use **drive-time isochrones**, which overlap, and the Huff split shares an overlapping cell between the suppliers that reach it. `shared_share` still shows the raw overlap (see 11) |
| **Index of Retail Saturation** | Demand × spend ÷ supply | The growth areas' **premium reviews per 1k women** is an IRS-like supply ÷ demand ratio, inverted, with **no spend term**. It is shown as context, not tested |
| **MCDA / weighted overlay** | Score sites on several criteria with stated weights | The lounge scorecard **is** one: two signals (demand percentile, rent ratio) ranked within each emirate's frozen market of competitor salon sites, equal weights. The reference set, scales and weights are judgement (see 10); the confidence flag tests the three live assumption levels (drive time, competitor coverage, worker share) and each weight ±25%, not the reference |
| **MCLP / location-allocation** | Pick the *set* of new sites that maximises coverage together | We score each growth area **independently** with a one-site what-if, so two GROW areas near each other could cannibalise each other, and a big area may hold more than one site (see 8) |
| **Analog / sales regression** | Predict a site's sales from comparable stores' revenue | Needs per-lounge revenue, which we don't have. **This is the main reason the scorecard is a proxy** (see 1) |
