# Limitations of the v3 model

The model is a first pass, and we expect to iterate on it. **Read this before trusting any call.**
The calls (PROTECT / HOLD / SHRINK for lounges, GROW / WATCH / SKIP for areas) are a shortlist
to test with the business, not decisions. Each limitation below says three things: which way it
biases the result, which calls it touches, and what would fix it. They are ordered by how much
they could change what the model says.

Data sources and their own caveats: `data/seed/v3/SOURCES.md`. The notebooks show every step:
`market_size`, `catchments`, `competitors`, `features`, `decisions` and `explanations`.

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

## 3. The calls depend on the assumptions

The model has three assumption levels: travel time (10/15/20 min), competitor coverage
(50/60/70%) and worker-housing female share (1%/5.5%/15%). Travel time matters most: 20 min
roughly doubles most catchments compared with 15 (median ×1.86), and 10 min shrinks them to about
a third.

- **10 of 23** scored lounges are **low confidence**: within 0.05 of a threshold, missing an input,
  a thin market, or a call that changes in 9 or more of the 27 level combinations. shahama flips
  in 21 of 27, mohammed-bin-zayed-city in 18, al-maqta in 12, and al-barsha and city-walk in 9.
- The app's what-if panel switches the levels, so you can watch a lounge move.
- **Fix:** evidence on how far UAE women actually travel to a salon (a customer postcode sample
  from Bedashing's bookings would settle it).

## 4. Drive times are midday, with no distance decay

Catchments are Mapbox drive-time polygons at **typical weekday-midday traffic**. TomTom 2025 puts
Dubai evening trips ~40% slower, so after-work catchments, when salon demand peaks, are smaller.
Inside the polygon every woman counts fully. Outside it, nobody counts. Mall lounges probably draw
from further away.

- **Touches:** demand, cannibalisation and the growth areas.
- **Fix:** rush-hour isochrones as a sensitivity (`isochrone_depart_at` 18:00, ~$0 within
  Mapbox's free tier), then distance decay (Huff).

## 5. The market-size estimate is coarse

Women 15+ per ~2 km cell come from WorldPop adults. WorldPop's sex split is one national ratio
(33.6% female everywhere), so we rebalance: worker housing (OSM industrial land) gets 5.5% women,
calibrated on Dubai labour-camp communities. Against 21 measured Dubai communities, this cuts the
error from 0.21 to 0.13.

- Camps not mapped as industrial in OSM are missed: Dubai Investment Park, Ras Al Khor Industrial
  and very likely Sonapur. **Mirdif-35's market is overstated.**
- There's no income, nationality or age mix. A premium lounge's real market is a slice of these
  women.
- Cell membership is decided by the cell's centre point, on a ~2 km grid.
- **Fix:** Dubai/Abu Dhabi statistics-centre community data with the sex split (where published),
  and an affluence layer (rents, villa share or property prices) to weight the women.

## 6. The competitor search misses salons

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

## 7. Growth areas are a first cut

Growth areas are populated cells beyond a 15-min drive of every lounge, grouped by OSM place name
and split into contiguous pieces.

- **Competitor data is partial.** Cells outside the catchments were searched only where they hold
  2,000+ women. Areas with under 50% of their women searched are capped at WATCH, and their
  saturation is computed over the searched cells only. 539 of 580 areas are SKIP; most are small.
- **The saturation line (50 premium reviews per 1k women) was set from the data it judges.** It
  sits well below the least crowded working catchment (88) and above most growth areas (median 5).
  Al Jerf (59) and Kalba (44) sit near it.
- **All 4 GROW areas are in Sharjah emirate** (Sharjah, Al Dhaid, Khor Fakkan, Kalba). All are beyond a
  15-minute drive of Bedashing's two Sharjah lounges (al-jada, zawaya-walk), both on the Dubai
  side; the "Sharjah" area's centre is ~13 km from al-jada. The business question is why the
  Sharjah footprint is only two lounges. The model can't see licensing, brand fit,
  landlord terms or customer mix. "Sharjah" is one 91k-women area. It's contiguous, so it wasn't
  split, and it may support more than one site.
- Distance to the nearest lounge is a straight line, not a drive.
- **Fix:** competitor searches for the remaining cells (~2,000 calls), drive-time catchments
  around candidate sites, and a business view on why Sharjah has only two lounges.

## 8. The rating signal is weak

Google ratings come in 0.1★ steps, and lounges span only 4.4-4.9★. The rating gap (lounge minus
its substitutes' median) takes six values. It counts at **half weight**. Most lounges rate slightly
below their substitutes (the median gap is −0.1★); we checked, and this is not caused by the
premium filter.

## 9. The scorecard's anchors were calibrated on the data they score

The fixed scales (0 → 200k women, 0 → 15% capture, ±0.3★, and the PROTECT/SHRINK lines at
0.65/0.35) were set on 2026-10-09 from these 23 lounges at medium levels, and reviewed by the
user. They are judgement, not benchmarks. A different, equally defensible anchor moves lounges
near the lines. That is why the low-confidence flag exists.

## 10. Cannibalisation is a symmetric share

`shared_share` is the share of a lounge's catchment women that another lounge also reaches. It
penalises both lounges in an overlap equally. It doesn't model where the customers would go if one
closed. Closing a lounge in the what-if panel makes its neighbours look better, by construction.
Abu Dhabi city lounges share 85-100% of their women.

## 11. Excluded and special cases

- **zayed-international-airport** is NOT SCORED: it serves travellers, not the women around it. It
  stays on the map, and its catchment still counts as "reached" for the growth areas.
- **New lounges** (e.g. noya-plaza): see 2. Lifetime reviews understate them.

## 12. The explanations

The AI explanations were written in a Claude Code session from the same prompts the API would get
(`python -m src.explain prompts|check|ingest`), not by the API. The grounding check verifies every
number and cited value against the fact sheet, but not adjectives, and not numbers spelled out as
words. A changed number falls back to the deterministic template. Areas marked SKIP and the airport
always use the template.

## 13. Freshness

Google data was fetched 2026-10-08/09. Google's terms allow storing only `place_id` indefinitely;
the rest should be refreshed within 30 days. WorldPop is the 2025 release; OSM is a 2026-07-28
snapshot.
