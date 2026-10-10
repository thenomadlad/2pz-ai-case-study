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

Capture also falls as competition rises. Across lounges, catchment women and capture have a
Spearman correlation of **−0.74**: big Dubai markets are crowded, so the lounge's share there is
tiny (about 1%, 0.8-1.6%, at al-barsha, city-walk, jumeirah-park and nad-al-sheba). Demand and capture
partly cancel, and a big crowded market tends to land in HOLD. We considered replacing both with
one "estimated customers" signal and rejected it, because it turned four of the five Dubai
lounges into SHRINK (`decisions.ipynb`, open question a).

- **Touches:** the capture signal (1 of 3.5 weight), and so every composite.
- **Fix:** a better share-of-customers measure: booking-platform data, card-spend panels, or
  footfall (e.g. mobile location data). A Huff gravity model (each woman's spend split across
  salons by attractiveness ÷ distance) would replace both catchments and capture.

## 3. Affluence is observed in Dubai only

Demand counts **addressable women**: each cell's women weighted by how its median household rent
compares with the women-weighted median (`(rent / median) ^ elasticity`, clipped to 0.25-4 before
rescaling to a mean of 1 over the observed cells; final weights 0.44-2.54 at medium, 0.18-2.68 at
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
  relative to non-Dubai ones. All 7 SHRINKs are in Abu Dhabi, the part affluence can't see. The
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
  a thin market, or a call that changes in a third or more (27+) of the 81 level combinations.
  shahama flips in 63 of 81, mohammed-bin-zayed-city in 54, al-maqta in 36, and al-barsha and
  city-walk in 27. The affluence level moves no lounge on its own, so these are three times the
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
- **Thin markets:** al-dhafra and al-falah have under 10 premium salons, so their capture is
  scored neutral (0.5) and their calls are low confidence.
- **Fix:** a full sweep of the capped circles (~1,600-6,000 calls; free from 1 November, ~$54-210
  now; declined 2026-10-09), and Bedashing's real price level from its booking pages.

## 8. Growth areas are a first cut

Growth areas are populated cells beyond a 15-min drive of every lounge, grouped by OSM place name
and split into contiguous pieces.

- **Competitor data is partial.** Cells outside the catchments were searched only where they hold
  2,000+ women. Areas with under 50% of their women searched are capped at WATCH, and their
  saturation is computed over the searched cells only. 539 of 580 areas are SKIP; most are small.
- **The saturation line (50 premium reviews per 1k women) was set from the data it judges.** It
  sits well below the least crowded working catchment (88) and above most growth areas (median 5).
  Al Jerf (59) and Kalba (44) sit near it.
- **Al Awir (Dubai) is a WATCH whose size passes only on thin affluence data** (see 3): 19.4k
  women, 20.1k addressable at medium, against a 20k line, with rents for 38% of its women.
- **All 4 GROW areas are in Sharjah emirate** (Sharjah, Al Dhaid, Khor Fakkan, Kalba). All are beyond a
  15-minute drive of Bedashing's two Sharjah lounges (al-jada, zawaya-walk), both on the Dubai
  side; the "Sharjah" area's centre is ~13 km from al-jada. The business question is why the
  Sharjah footprint is only two lounges. The model can't see licensing, brand fit,
  landlord terms or customer mix. "Sharjah" is one 91k-women area. It's contiguous, so it wasn't
  split, and it may support more than one site.
- Distance to the nearest lounge is a straight line, not a drive.
- **Fix:** competitor searches for the remaining cells (~2,000 calls), drive-time catchments
  around candidate sites, and a business view on why Sharjah has only two lounges.

## 9. The rating signal is weak

Google ratings come in 0.1★ steps, and lounges span only 4.4-4.9★. The rating gap (lounge minus
its substitutes' median) takes six values. It counts at **half weight**. Most lounges rate slightly
below their substitutes (the median gap is −0.1★); we checked, and this is not caused by the
premium filter.

## 10. The scorecard's anchors were calibrated on the data they score

The fixed scales (0 → 200k addressable women, 0 → 15% capture, ±0.3★, and the PROTECT/SHRINK lines at
0.65/0.35) were set on 2026-10-09 from these 23 lounges at medium levels, and reviewed by the
user. They are judgement, not benchmarks. A different, equally defensible anchor moves lounges
near the lines. That is why the low-confidence flag exists.

## 11. Cannibalisation is a symmetric share

`shared_share` is the share of a lounge's catchment women that another lounge also reaches. It
penalises both lounges in an overlap equally. It doesn't model where the customers would go if one
closed. Closing a lounge in the what-if panel makes its neighbours look better, by construction.
Abu Dhabi city lounges share 85-100% of their women.

## 12. Excluded and special cases

- **zayed-international-airport** is NOT SCORED: it serves travellers, not the women around it. It
  stays on the map, and its catchment still counts as "reached" for the growth areas.
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
