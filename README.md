# Bedashing network right-sizing

Bedashing runs 24 beauty lounges across the UAE and has to decide which sites to keep, which to
look at again before their leases come up, and where a new lounge would win women it doesn't
reach today. This app helps with both: what to do with each lounge (protect, hold or shrink) and
where to open next (grow, watch or skip). It is built from three parts:

1. **A decision model** that makes every call from public data: how many women a typical lounge
   would serve at each site, against the competing salons, and what the site costs in rent, judged
   against the other salon sites in its emirate ([Decision model](docs/decision-model.md)).
2. **An LLM explanations model** that turns each call into a short, checked explanation for the
   decision-maker and the board: the answer first, then the reasons, every number verified against
   the data ([LLM explanations model](docs/llm-explanations.md)).
3. **A what-if loop:** change the assumptions, the decision rules or a site's rent, or close a
   lounge, and every call is re-run on the spot, with what moved shown against the baseline (the
   What-if explorer).

At today's settings it is surest about three moves: review 1 lounge (City Walk; review, not close),
defend 3 and run a site search in 12 areas. Counting its lower-confidence calls too, that is 3, 6
and 34. Terms such as site demand and rent ratio are defined in the [Glossary](docs/glossary.md).

**Live app:** https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/

## Walkthrough (5 minutes)

A guided path through the live app: the answer, one lounge decision, one growth call and a scenario.

1. **[Executive Summary](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/):** the answer in one line, then the Review, Protect and Grow cards (high-confidence calls only) and their evidence maps and tables.
2. **[What-if explorer](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/explore):** pick Abu Dhabi: every lounge's catchment is drawn, shared cells in red. Heavy overlap, yet only West Yas is SHRINK.
3. **[City Walk](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/lounge?lounge=city-walk) (SHRINK):** the AI pyramid, *What would change the call*, the factor tree and which siblings share its women. *Action:* lease review, with finance's P&L before anyone says "close"; a prime rent may be buying footfall the model can't see.
4. **[Kalba](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/area?area=kalba-sharjah) (GROW, low confidence):** about 12.5k net new women, but no shop rent of its own, and the call says so.
5. **Back on the What-if explorer:** open the 🧪 panel, quote City Walk a rent of 2,200 and watch its call move.
6. **Documentation** (sidebar): this [README](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/how), then the Decision model, LLM explanations model, App and implementation, Limitations and Glossary pages.

## Who it's for, and what it decides

**Who decides:** the network and capital owner, on the retail portfolio team. They decide where
Bedashing is present and how much capital each site ties up: open, renew, resize, relocate or exit.
How much capacity each catchment needs (service providers and hours) is their call too. They don't
run the branches: service quality, rosters, hiring and day-to-day performance belong to operations.

| Role | Who | Uses it to |
|---|---|---|
| **Primary user** | Bedashing's retail portfolio team (network, real estate, expansion) | form recommendations, stress-test them with what-ifs, lift the explanations into memos |
| **Decision-maker** | The network and capital owner, on the portfolio team | open, renew, resize, relocate or exit, from the headline and the reasons |
| **Operations** (out of scope) | Whoever runs the branches: service quality, rosters and hiring, day-to-day performance | nothing here: the tool never judges how a branch is run |
| **Board / investors** | Bedashing's board and investors | judge whether the call is defensible: evidence, thresholds, caveats |

Each label maps to a decision the network and capital owner already makes (definitions: [`docs/glossary.md`](docs/glossary.md), "Decisions"):

| Their decision | Label | What it asks |
|---|---|---|
| **Lease renewal, resize or exit** (each lounge, at its lease event) | **PROTECT** | Keep and defend: renew, don't relocate, respond to a competitor opening nearby |
| | **HOLD** | No portfolio action this cycle; revisit at the next lease event, or sooner if a signal crosses a line |
| | **SHRINK** | Investigate, don't close: before the lease event, review downsizing; consolidate only where a sibling would take most of its customers (City Walk's siblings would take about 1%) |
| **Open** (site search, expansion plan) | **GROW** | Start a site search: a shortlist for site visits, verified on the ground before committing |
| **Revisit later** | **WATCH** | Don't act now; revisit when the named failing test changes |
| **No action** | **SKIP** | Too small or already crowded. (The airport lounge is NOT SCORED: it serves travellers.) |

**North star: services sold** (completed appointments), judged per catchment and capped by
capacity. The model can't measure it yet: its nearest proxy is served women (a model
estimate of the customers behind the services a lounge sells), shown as context, and
**capacity is not modelled at all** (no chairs, hours or utilisation), so a SHRINK is driven by
modelled demand and shop rent, not by services that would be lost.

## The questions it helps answer

A decision-support system for Bedashing's **retail portfolio team** (network, real estate,
expansion) and the **network and capital owner** on it. It doesn't hand down answers: for each
question the team keeps coming back to, it gives a recommendation, the evidence behind it, how sure
to be, and a way to test it. Below, what it suggests at the baseline (15-min drive, 60% competitor
coverage, 5.5% women in worker housing, affluence off); every count of women is a model estimate.

1. **Which lounges should we keep, watch or review?**
   It scores every lounge's site on demand and rent within its emirate. At the baseline:
   **6 PROTECT, 14 HOLD, 3 SHRINK** of 23 scored lounges (the airport lounge serves travellers and isn't scored).
   - PROTECT: Al Ain, Al Dhafra, Al Falah, Al Taif Mall, Mirdif 35, Nad Al Sheba.
   - SHRINK (investigate, don't close: we can't see profit): City Walk (bottom 30% of Dubai's salon
     sites on demand, rent ratio 0.47), West Yas (bottom 45% of Abu Dhabi's, 0.82) and Al Jada (top
     34% of Sharjah's on demand, but rent ratio 0.63: it sits on the dear Dubai edge of Sharjah).
   - 12 of the 23 calls are low confidence: close to a line, on a fallback rent, or moved by the
     assumptions (see Limitations).
   - **Where to look:** the Executive Summary's Review and Protect sections; the Lounges page for every lounge and its "What would change the call" tree.
2. **Where is there room for a new lounge?**
   It opens a typical lounge at every named place and counts the women it would add. At the baseline,
   **34 GROW areas** (and 63 WATCH, of 561 named places) pass all three tests: 6,000+ net new women, site demand in the emirate's top half, and a rent ratio of 1 or more.
   - By emirate: Abu Dhabi 13, Sharjah 10, Ajman 6, Ras Al Khaimah 4, Dubai 1 (Al Awir).
   - The biggest are Al Dhaid (+35% on the women our lounges serve today), Manama (+21%) and Khor Fakkan (+14%).
   - These figures can't be added up: neighbouring areas reach the same women.
   - 17 of the 34 have no shop rent of their own (they take the emirate median), so their rent test is neutral and the call low confidence.
   - Most Sharjah GROWs are beyond a 15-minute drive of our two Sharjah lounges (Al Jada, Zawaya Walk, both on the Dubai side); why the footprint there is two is a business question the model can't answer.
   - Most big WATCHes (Al Dhahir, Bani Yas, Al Helio) have the women but a rent dearer than their emirate's median salon site.
   - **Where to look:** the Executive Summary's Grow section; the Areas page; the What-if explorer's map (GROW areas in blue).
3. **Where do our own lounges compete for the same women?**
   It shares each area's women among every salon that reaches them, our lounges included, and shows
   what a closure would hand to the siblings. At the baseline: almost everywhere on the map, yet barely
   in effect.
   - 19 of 24 lounges share more than half their catchment with a sibling.
   - If one closes, its siblings pick up a median **8%** of its customers (30% at most). The rest go to competitors or nowhere.
   - **Lounges sharing a catchment both keep their call while women there go unserved.** A sibling only counts against a site for the women it actually wins; women still unserved, or with competitors, still count toward the site's demand. Of the 18 lounges sharing more than half their catchment, 15 are HOLD or PROTECT, and the 3 SHRINKs are there for rent or weak demand, not overlap. Khalifa City A, Shakhbout City and Mohammed Bin Zayed City share 97-100% of their catchments and are all HOLD.
   - **A new lounge can still be GROW inside our footprint**, judged on net new women only: 15 GROW areas are places our lounges already reach, such as Sharjah city (we serve 3% of its women; a new lounge would add about 12.8k net new).
   - So overlap isn't a reason to shrink, and expanding both lounges in a shared catchment can be right if it raises our coverage.
   - **Where to look:** each lounge page's shared-catchment table and cannibalisation what-if; the What-if explorer's map, which always draws every lounge's catchment (shared cells in red), and **Test a SHRINK**.
4. **How does each lounge stand against the salons around it?**
   It ranks each site against its emirate's competitor salon sites. Site demand shares every area's women among our lounges and the 1,100+ premium competitor salons around them, in proportion to how much each sells (measured by its Google reviews, our proxy for services sold; a service sold = one completed appointment), then ranks the site against its emirate's competitor salon sites.
   - Example: City Walk out-serves only 30% of Dubai's salon sites; Al Dhafra out-serves all of Abu Dhabi's.
   - How much a lounge sells against its site is shown beside the call, not scored: "The model estimates this lounge is performing 2.7x compared to its site" (Khalifa City A, a HOLD): it sells 2.7x what a typical lounge would at its site, which separates a strong lounge from a strong location.
   - **Where to look:** each lounge page's signals, factor tree and competitors table; premium competitors on the What-if explorer's map.
Every answer can be tested. On the **[What-if explorer](https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/explore)**
the team sets its own decision rules (the weight of demand against rent, the PROTECT and SHRINK
lines, the GROW bar), plugs in a landlord's rent quote, closes lounges, or changes the model's
assumptions (drive time, competitor coverage, worker housing), and sees the baseline against the
scenario with every call that moved. For example, a rent quote of AED 2,200/m² turns City Walk from
SHRINK to HOLD, and a GROW bar of 10,000 net new women cuts GROW from 34 areas to 16.

## Limitations

The calls are **a shortlist to test with the business, not decisions**, and the limitations matter
more than the calls. The biggest ones:

- **No revenue or lease data in the model.** Site cost should be the real rent for the space a lounge
  needs to serve its catchment; the model only has a shop rent per m² (an area median, a district
  rate or an asking rent, not the lease), compared with its emirate's median salon site. The model
  has none of the revenue, fixed cost base, profitability, capacity, capacity utilization and other
  branch health KPIs which are key for this model to provide more definitive recommendations; [the model we'd build with them](docs/decision-model.md#the-ideal-model-the-same-decisions-on-bedashings-own-metrics)
  is in the model notes. **SHRINK means "investigate", not "close".**
- **Services sold are measured by lifetime Google reviews.** Each review is a trace of past
  appointments, so a salon's reviews stand in for how much it has sold, and its share of the Huff
  split follows them. Lifetime counts favour older salons and new lounges look weak; review rates
  differ between salons and services; it is a stand-in until bookings data. The Huff parameters are
  an uncalibrated first cut.
- **Shop rent comes from different sources per emirate.** DLD contracts (Dubai), ADREC district
  rates read by hand off its public map (Abu Dhabi), Property Finder / Bayut asking rents scraped
  via third-party Apify actors, a grey area under those portals' terms (northern emirates), else the
  emirate median. The rent ratio compares a site only with its own emirate's salon sites. A cell on
  the emirate-median fallback has no rent of its own, so where it sets the rent the rent test is
  neutral and the call low confidence: 17 of the 34 GROW areas (9 in Sharjah) and two PROTECT
  lounges (Al Ain, Al Falah).
- **The calls move with the assumptions.** 12 of the 23 scored lounges are low confidence: 10
  within 0.05 of a line, plus Al Ain (fallback rent) and Jumeirah Park, whose calls change in 9 of
  the 27 drive-time x coverage x worker-share combinations. Affluence weighting is off at baseline: every woman counts the same.
- **Drive times are midday**, and the competitor search misses smaller salons where Google's
  20-result cap bites.
- **The yardstick and thresholds are judgement.** Both signals rank a site within its emirate
  against a frozen set of 1,123 competitor salon sites, valued by the same uncalibrated served model;
  emirates with under 50 such sites are ranked UAE-wide on demand. Every score is shown with its
  UAE-wide percentile as context.
- **Keep and grow use different bars.** Keep or shrink is judged within the site's emirate, but a
  growth area needs an absolute 6,000 net new women, so a PROTECT site can fail the growth test as a
  new opening: Nad Al Sheba is PROTECT (it out-serves 68% of Dubai salon sites), yet a typical lounge
  there would serve about 2,700 women.
- **Sharjah's GROW areas are mostly beyond our footprint.** 10 of the 34 GROW areas are in Sharjah
  emirate, and 9 of them are beyond a 15-minute drive of our two Sharjah lounges (Al Jada, Zawaya
  Walk), both on the Dubai side; only Sharjah city itself is close (2.5 km from Al Jada).
  Why the footprint there is only two lounges is a business question: the model can't see licensing,
  brand fit, landlord terms or customer mix.

The full ranked list, with which calls each limitation touches and what would fix it:
[`docs/limitations.md`](docs/limitations.md).

## Out of scope, and why

Our job ends at **allocating lounges to neighbourhoods**: where the network should be denser,
thinner or new. Out of scope:

- **The P&L: revenue, actual rent paid, capex, lease terms.** We have none of it, and it is Bedashing's own
  data. It decides whether a SHRINK is closed; the model only says which lounges to look at.
- **Running a branch day to day: rosters, shifts, hiring and managing individual staff.** How much
  capacity each catchment needs (service providers × hours) is in scope, since it decides where
  branches and providers go, but today's model can't measure it: that needs bookings and headcount
  data (see [the model we'd build with Bedashing's data](docs/decision-model.md#the-ideal-model-the-same-decisions-on-bedashings-own-metrics)).
- **Service quality and operations.** Ratings enter only as a factor on each salon's services sold
  in the Huff split; fixing a weak lounge's service is a management job, not a location one.

## Documentation

The detail lives in five documents, each a page under **Documentation** in the app's sidebar:

- **[Decision model](docs/decision-model.md):** the model we'd build with Bedashing's data, the proxies
  that stand in for it today, and what we built: how a call is made step by step, the diagrams, every
  factor we ignore and why, and every assumption with its evidence (with live values from the code in
  the app).
- **[LLM explanations model](docs/llm-explanations.md):** why every call comes with a written
  explanation, how it is made and checked, and why it is precomputed here and live in production.
- **[App and implementation](docs/app-and-implementation.md):** running the app, how I approached it,
  how we checked it, the data, tools, trade-offs, potential improvements and a repo map.
- **[Limitations](docs/limitations.md):** the full ranked list, which calls each one touches and what
  would fix it.
- **[Glossary](docs/glossary.md):** the domain terms and what each call means.

To run it locally: `uv sync --extra dev`, then `uv run streamlit run streamlit_app.py`
([details](docs/app-and-implementation.md#running-this-app)).
