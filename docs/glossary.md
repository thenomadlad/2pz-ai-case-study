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

**Affluence (rent) index**:
A cell's median annual household rent (AED): DLD Ejari contracts for one flat, villa or studio,
registered 2026-07-10 to 2026-10-09, median per DLD area, mapped to cells. Observed for 241 Dubai
cells only (`rent_observed`, `affluence_source`); every other cell has none and is weighted neutral.
Housing cost, not income or salon spend. Used only by the affluence what-if: off at baseline.

**Shop rent**:
Commercial rent per m² a year (AED) at a lounge's site (`site_rent_m2`), or over a catchment or area. It is **our cost**, not customer affluence.
- **Dubai:** DLD Ejari shop contracts.
- **Abu Dhabi:** ADREC 2025 street-retail rate for the cell's district, read by hand off ADREC's
  public map (its data service refuses queries).
- **Northern emirates:** median asking rent of nearby Property Finder / Bayut shop listings, scraped
  via third-party Apify actors (a grey area under the portals' terms of service).
- **Everywhere else:** the emirate median.

It feeds the rent ratio (the scorecard's cost signal and the GROW rent test) and the site cost (display only).
_Avoid_: rent (unqualified); it's ambiguous with the affluence rent.

**Site cost**:
A site's annual cost in AED 1k (`site_cost_k`): shop rent x an assumed 150 m² unit + an assumed
fit-out of AED 3,000/m² written off over 5 years. Display context only: no call uses it.

**Site reference**:
The frozen market of salon SITES every lounge and area label is judged against
(`data/seed/v3/site_reference.csv`, built once 2026-10-11 by `scripts/build_site_reference.py`):
1,123 real premium competitor salons (no imputed ones, no Bedashing), each with its emirate, cell
shop rent and `ref_served`, the women a typical lounge (757 reviews, 4.6 stars) would serve there
with all our lounges open. Dubai 582, Abu Dhabi 304, Sharjah 143, Ajman 38, Ras Al Khaimah 33,
Fujairah 18, Umm Al Quwain 5. Never our own lounges; nothing we open or close moves it.
_Avoid_: benchmark, peer group (our lounges are not in it)

**Demand percentile**:
The share of its emirate's reference sites a site out-serves (`demand_pct`, 0..1; for a lounge on
site served, for an area on the what-if lounge's served women). It is the scorecard's demand score
and a GROW test (0.5+). Emirates with under 50 reference sites (Ajman, Ras Al Khaimah, Fujairah,
Umm Al Quwain) are ranked UAE-wide (`demand_ref` = "UAE"). Shown with its UAE-wide percentile
(`demand_pct_uae`) as context: "top 20% of Dubai salon sites on demand · 45th percentile UAE-wide".

**Rent ratio**:
The emirate's median shop rent at its reference sites ÷ the site's shop rent (`rent_ratio`; above 1 =
cheaper than the median salon site in its emirate). Always against its own emirate, even under 50
sites. The scorecard's cost signal on a frozen scale (P10 0.62 → 0, P90 1.43 → 1) and a GROW test
(1+, unknown passes). Rent only: served women are not in it. Shown with its UAE-wide rent percentile
(`rent_pct_uae`, higher = dearer) as context.
_Avoid_: ROI, return, profitability, cost efficiency

**Women per rent**:
Addressable women per AED 1,000 of a site's annual shop rent, for an assumed 150 m² unit (`women_per_rent_k`). Shown as context; not scored.
_Avoid_: income, wealth, spend, affluence score (unqualified)

**Addressable women**:
Women 15+ x the cell's affluence weight, `(rent / women-weighted median rent) ^ elasticity`, clipped
to 0.25-4 before rescaling to a mean of 1 over the observed cells (final weights 0.44-2.53 at
medium); 1 where no rent is observed.
Elasticity off 0 / medium 0.5 / strong 1. **Off at baseline** (0: weight 1 everywhere, so addressable
= raw women); kept as a what-if. Served demand is built on it; catchment women and an area's women
stay raw. Cannibalisation (`shared_share`) and growth
saturation (premium reviews per 1k women) also use raw women: they measure overlap and crowding
of everyone a lounge or salon serves, and weighting them would count the same women differently
in numerator and denominator.
_Avoid_: premium women, target market, weighted demand (unqualified)

**Served women**:
The addressable women a lounge serves in the Huff split: each cell's women divided across the premium
suppliers that reach it within 20 min (our lounges and premium salons, pull = reviews x a rating
factor x drive-time decay) plus an outside option, summed over cells (`served_women`). Context,
not scored.
_Avoid_: catchment women, customers

**Site served**:
The women a typical lounge (median reviews and rating) would serve at a lounge's site, with that
lounge closed and siblings and rivals open (`site_served`). Ranked against the site reference, it is
the scorecard's demand signal (see Demand percentile): it judges the site, not the lounge.

**Performance vs site**:
Served women / site served (`performance_vs_site`). Context, not scored: "The model estimates this
lounge is performing 2.7x compared to its site."

**Net new women**:
For a growth area: the women a typical new lounge at its centre would serve, minus what it takes from
our existing lounges (`new_site_net`). The GROW size test.

**Growth area**:
The populated cells beyond a 15-min drive of every open scored lounge that share an OSM place name
(and emirate): one area per named place, whether its cells touch or not. Cells named only by their
emirate (no OSM admin boundary or place within 3 km, `name_source == "emirate"`) make no area:
nothing actionable is known about where they are. They still count in catchments, overlap and
population totals. Labelled GROW / WATCH / SKIP.
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
share of the catchment's premium reviews. Other Bedashing lounges count too, except the NOT SCORED
airport lounge.
_Avoid_: competitor (when the premium set is meant), top-k

**Coverage**:
The share of a catchment's premium reviews the substitutes must hold: 60% (50% / 70% as
sensitivity). Sets how many substitutes a lounge has.
_Avoid_: k, top-n

**Capture**:
The lounge's Google reviews ÷ (its own + its substitutes' reviews, scaled up by the search-recall
correction). A proxy for its share of premium customers in its catchment, not market penetration.
Shown, not scored (served demand already splits by reviews).
_Avoid_: market share, fair share

**Rating gap**:
The lounge's Google rating minus the median rating of the premium salons in its catchment with 20+
reviews (the whole premium pool, not the substitutes: their number grows with the pool, so one added
salon could change which ones count). Shown, not scored; the rating enters served demand through
each supplier's pull.
_Avoid_: substitutes' median

**Search recall**:
The estimated share of premium reviews our search finds where its circles hit Google's 20-result
cap (0.66, calibrated on one fully swept tile). Substitutes' reviews are scaled up by it where the
cap bites.
_Avoid_: coverage (a different thing)

**Cannibalisation**:
The share of a lounge's catchment women that another open scored lounge also reaches (`shared_share`);
the NOT SCORED airport lounge is never a sibling. Shown, not scored, with the absorbed share (the
share of its served women siblings would take over if it closed, `absorbed_share`); closing a lounge
is a what-if on the lounge page.
_Avoid_: contested share, overlap (unqualified)

### Decisions

**Lounge action**:
PROTECT, HOLD or SHRINK from the scorecard; NOT SCORED for the airport lounge. What each one asks
the network and capital owner to do:
- **PROTECT**: keep and defend the site. Renew at the lease event, don't relocate, and treat a
  competitor opening nearby as a threat to respond to.
- **HOLD**: no portfolio action this cycle. Revisit at the next lease event, or sooner if a signal
  crosses a line (the lounge page names which one is closest).
- **SHRINK**: investigate, don't close. Before the lease event, review whether to downsize or
  consolidate into the sibling that shares most of its catchment. The model has no revenue or lease data,
  so it can only raise the question.

**Growth action**:
GROW, WATCH or SKIP, assigned to a growth area from a what-if: open a typical lounge here.
- **GROW**: start a site search here. 6,000+ net new women, worker housing under 50%, a rent ratio
  of 1+ (or unknown) and a demand percentile of 0.5+ in its emirate's salon sites. It's a shortlist for a site visit and lease search, to be verified on the
  ground before committing.
- **WATCH**: don't act now. Big but dearer than its emirate's median salon site or with weaker demand, big but mostly worker housing,
  or 3,000+ net new women. Revisit when the named failing test changes.
- **SKIP**: no action. Under 3,000 net new women, under 5,000 women, or non-residential by name
  (industrial, free zone, military, airport, port).

**Low confidence**:
A lounge call within 0.05 of a threshold, or that **flips**: changes in a third or more (27+) of the 81 combinations of the four assumption
levels (travel time, coverage, worker-housing female share, affluence elasticity), or under any
single signal weight moved ±25% (in practice that only catches calls already within 0.05 of a line).
For a growth area, low / medium / high: low within 10% of the 6,000 net-new-women line or with
under half its women searched; high when 20%+ clear of it.
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
The network and capital owner, on the portfolio team. Decides where Bedashing is present and how much capital each site ties up: open, renew, resize, relocate or exit. Doesn't run the branches: service quality, staffing and day-to-day performance belong to operations, so every call answers "is this a good place to have our capital?", never "is this branch well run?".
_Avoid_: leadership, user, a job title

**Board**:
Bedashing's board and investors, who must be persuaded that a decision is defensible.
_Avoid_: naming an owner or fund (unsourced); the board as the user
