# Bedashing network right-sizing

Decision support for Bedashing Beauty Lounge's UAE network: which lounges to protect, hold or
investigate, and where to grow. The calls are a shortlist to test, not decisions
(`docs/limitations.md`).

## Language

### Network and geography

**Lounge**:
An open Bedashing location; 24 in the UAE (`data/seed/v3/branches.csv`). The code calls its id
`branch_id`.
_Avoid_: store, site, outlet

**Cell**:
A ~2 km grid cell carrying women aged 15+ (WorldPop adults, rebalanced for worker housing). The unit
of market size. Replaces the 50 Dubai communities of the old model.
_Avoid_: community, district, neighbourhood, hex

**Catchment (drive-time)**:
The cells whose centre is within a 15-min drive of a lounge (10 / 20 min as sensitivity), from
Mapbox isochrones at typical weekday-midday traffic. Catchment women = the sum of its cells' women.
_Avoid_: service area, trade area, radius, nearest-branch catchment

**Growth area**:
A contiguous piece of populated cells beyond a 15-min drive of every open lounge, grouped by OSM
place name. Labelled GROW / WATCH / SKIP.
_Avoid_: opportunity area, whitespace, candidate site

**Competitor**:
A women's beauty, hair or nail salon from Google Places (men-only, closed and non-salon places
excluded, with a reason).
_Avoid_: rival, POI

### Competition and share

**Premium substitute**:
A premium salon in a lounge's catchment that a Bedashing customer would compare it with. Premium =
Google price expensive or above, or, without a price, at least the catchment's median reviews and
rated 4.3+. The substitutes are the most-reviewed premium salons that together hold the coverage
share of the catchment's premium reviews. Other Bedashing lounges count too.
_Avoid_: competitor (when the premium set is meant), top-k

**Coverage**:
The share of a catchment's premium reviews the substitutes must hold: 60% (50% / 70% as
sensitivity). Sets how many substitutes a lounge has.
_Avoid_: k, top-n

**Capture**:
The lounge's Google reviews ÷ (its own + its substitutes' reviews, scaled up by the search-recall
correction). A proxy for its share of premium customers in its catchment, not market penetration.
_Avoid_: market share, fair share

**Search recall**:
The estimated share of premium reviews our search finds where its circles hit Google's 20-result
cap (0.66, calibrated on one fully swept tile). Substitutes' reviews are scaled up by it where the
cap bites.
_Avoid_: coverage (a different thing)

**Cannibalisation**:
The share of a lounge's catchment women that another open lounge also reaches (`shared_share`).
_Avoid_: contested share, overlap (unqualified)

### Decisions

**Lounge action**:
PROTECT, HOLD or SHRINK from the scorecard; NOT SCORED for the airport lounge. SHRINK means
"investigate", not "close": the model has no revenue or rent.

**Growth action**:
GROW, WATCH or SKIP, assigned to a growth area.

**Low confidence**:
A lounge call within 0.05 of a threshold, with a missing input (thin premium market, no rating gap),
or that **flips**: changes in 9 or more of the 27 combinations of the three assumption levels
(travel time, coverage, worker-housing female share).
_Avoid_: uncertain, borderline (unqualified)

### Retired terms (the old Dubai model)

**Community**: one of 50 Dubai statistical communities. No longer the unit: cells replace it, and
growth areas replace "opportunity areas". Still used only for the Dubai Statistics Center
calibration of the worker-housing female share.

**Salon headroom**, **uncovered women**, **fair-share capture**: measures of the old model, gone with it.

### Audiences

The tool supports the conversation between these three roles.

**Portfolio team**:
Bedashing's network, real estate and expansion team and its analysts. The primary user: it uses the tool to form and defend recommendations.
_Avoid_: user, analyst (unqualified)

**Decision-maker**:
Bedashing's COO. Approves or questions the portfolio team's recommendations. Accountable for lounge operations and return on invested capital.
_Avoid_: leadership, user

**Board**:
The PE owner's board and operating partner, who must be persuaded that a decision is defensible.
_Avoid_: investor, PE firm (as the user)
