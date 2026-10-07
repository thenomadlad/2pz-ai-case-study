> **Historical record.** This was the README through v1 (rank-into-thirds rubric, no competitor data, an optional LLM decision backend). The current model is described in the top-level README; this file is kept for the development story, data-source research and decision register.

# Bedashing branch right-sizing

> **Fill convention:** every `> _Fill:_` blockquote is a prompt to replace with real content, then delete the prompt. `TODO` marks a section with nothing in it yet. Pre-filled lines marked `[confirm]` are decisions already taken in planning — verify before shipping.

One-line description: a decision-support tool for a Bedashing Beauty Lounge portfolio manager to decide which Dubai branches to protect, hold, or shrink — and to pressure-test that call against their own assumptions before acting on it.

---

## Quickstart

**Prerequisites**
- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) (dependency/venv management)
- No API keys required for the default path. `ANTHROPIC_API_KEY` switches the decision model from the deterministic rubric backend to an LLM backend; without it, everything automatically falls back to rubric. **Not recommended for a public deployment** — see *Where to trust this, and where not* below for why.

**Run it**

```bash
git clone git@github.com:thenomadlad/2pz-ai-case-study.git
cd 2pz-ai-case-study
uv sync --extra dev
uv run python -m src.scenario.baseline   # builds data -> features -> decisions (just all)
uv run streamlit run streamlit_app.py    # then open http://localhost:8501 (just app)
```

(`just all` / `just app` are shorthand for the two commands above if you have
[`just`](https://github.com/casey/just) installed — see `justfile`.)

**What you should see**

The Product page loads with a headline stating a PROTECT/HOLD/SHRINK count across the 9 real Dubai branches (e.g. "3 PROTECT, 3 HOLD, 3 SHRINK"), a caption reading "Backend: rubric", and a map below it with 9 colored branch markers. If instead you see a `FileNotFoundError` or a blank map, something's wrong — this path is meant to work from a clean clone with zero configuration.

**If you only have two minutes**

The live deployment: **https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/**

> _Fill:_ a recorded walkthrough (2-3 min) would be a stronger escape hatch than the live link alone — TODO, not yet recorded.

---

## The decision this supports

**Decision-maker.** TODO — a named role, not "leadership."
> _Fill:_ which role actually signs off, which role uses the tool day to day, and which role has to be persuaded. See *Business context* below — ownership/org structure is also TODO there, and these two TODOs are the same gap.

**Decisions in scope.**

| Decision | Trigger / cadence | Capital at stake | Reversibility |
|---|---|---|---|
| Continue backing a branch (PROTECT/HOLD) | Ad hoc portfolio review | TODO — no lease/capex data exists (see *Signals*) | High — no action taken |
| Reduce footprint at a branch (SHRINK) | Ad hoc review, or a SHRINK flip surfaced by a data/assumption update | TODO — unknown without lease-exit cost | Low once executed |
| Relocate an existing branch | Lease renewal/expiry | TODO | Low once executed |
| Evaluate a new site | Opportunity surfaced externally | TODO | High before signing — the model only informs, never commits, capital |
| Exit the Dubai market entirely | Not modeled | n/a | n/a |

Relocation and new-site evaluation are genuinely supported today — the scenario
mechanism (see *How to read the app*) lets you override an existing branch's
coordinates, or add a hypothetical branch with its own coordinates, and see where it
lands. What's **not** built is a distinct evaluation path for new sites — see the
taxonomy note immediately below.

**Objective function.** Not capital/ROIC-based today, and I want to be direct about
that rather than claim otherwise: the implemented objective is a composite rubric
score over three signals — population served, contested catchment share (inverted),
and rating — each network-normalized, averaged equally, then ranked: top third
PROTECT, bottom third SHRINK, middle HOLD (`src/model/rubric.py`). There is no
revenue, footfall, lease-cost, or invested-capital figure anywhere in the pipeline, so
there is nothing to compute a return-on-invested-capital or hurdle-rate comparison
*from* — see *Signals* below for exactly what's missing and why. Reframing this to a
true capital-deployment objective is the single highest-leverage next step, and it's
blocked on data, not modeling effort.

**How the recommendation taxonomy maps to the objective.**

The implementation uses **one** three-way taxonomy (PROTECT/HOLD/SHRINK), applied
identically whether the branch being scored already exists or is a scenario-introduced
hypothetical — there's no separate GROW/WATCH/SKIP scale for new sites. A hypothetical
branch that lands in the top third of the network, by the same rubric, gets PROTECT;
one that lands in the bottom third gets SHRINK. That's a real design simplification,
not an oversight: building a second taxonomy for new sites would need its own
justification (a new site has no track record to rank against; ranking it purely
against *existing* branches' current numbers may not be the right comparison), and
that justification hasn't been done.

| | Existing branch | New opportunity |
|---|---|---|
| Top third of the network by composite score | PROTECT | PROTECT (same scale, same threshold) |
| Middle third | HOLD | HOLD |
| Bottom third | SHRINK | SHRINK |
| Driven by an assumption that moves the tier (e.g. `contest_ratio`) | flagged in the scenario diff, not a separate label | same |

**Explicitly out of scope.**
- `[confirm]` Dubai only. Bedashing operates 23 branches UAE-wide; this model sees the
  9 in Dubai. A SHRINK call here can't see a sibling branch in Abu Dhabi or Sharjah
  absorbing the same demand, so a network-wide cannibalization story is invisible by
  construction.
- `[confirm]` No revenue, footfall, staffing, or lease-cost data anywhere in the
  pipeline — see *Signals* below for the full accounting of what's missing and what
  stands in for it.
- Nearest-branch demand assignment ignores travel time, malls, parking, habit, price,
  and brand loyalty — every community's full population is assigned to its
  straight-line-nearest branch, winner-take-all.
- No competitor data. The single biggest omission — a branch with five rival salons
  next door looks identical to one with none.
- LLM-backend decisions have no ground truth; agreement with the rubric is a sanity
  check, not validation.

---

## How to read the app

The app has four stages, in this order, and the UI follows the same order:

**Assumptions → Model → Scenarios → Decision**

| Stage | What it holds | Where it lives |
|---|---|---|
| **Assumptions** | Every input that is not computed from data — `contest_ratio`, `global_female_share`, `fallback_price_aed`, decision backend. Named, versioned, editable. | `data/scenarios/baseline.yaml` (baseline), `src/config.py` (defaults), the "Build a scenario" widgets on the Product page (live overrides) |
| **Model** | The computation from data + assumptions to per-branch features and a decision. Deterministic given its inputs (rubric) or disk-cached per feature-vector (LLM). | `src/features/assign.py`, `src/features/build.py`, `src/model/rubric.py`, `src/model/llm.py`, `src/model/run.py` |
| **Scenarios** | A named set of assumption overrides and/or structural changes (relocate an existing branch, add a hypothetical one) evaluated against the fixed baseline, in memory — never written back to baseline. | `src/scenario/apply.py`, `run.py`, `diff.py`; `data/scenarios/*.yaml` for CLI use; `src/webapp/scenario_editor.py` for the live UI |
| **Decision** | PROTECT/HOLD/SHRINK per branch, with rationale, key drivers, and caveats, plus a diff against baseline once a scenario has run. | `data/processed/<baseline\|current>/decisions.json`; `src/webapp/pages/product.py` |

The assumptions sit first, visible and editable, because the half of this problem
that actually determines the answer — population share, competitive overlap, what
counts as "contested" — is not sourced from outside the company; it's declared. The
tool's job is to be rigorous about what's computed and explicit about what's assumed,
not to pretend the assumptions aren't there.

---

# Development story

## v0 — a prototype to pressure-test the idea

**Goal.** Get an end-to-end path from data to a displayed decision, deliberately
crude, to find out whether the framing holds up before investing in the model.

### Roles defined
> _Fill:_ v0's own design doc (`docs/designs/v0.md`) frames this as "a working toy you
> can poke at within a day," built for someone who wants to argue with a model, not a
> finished deliverable for someone who needs to defend a decision to someone else.
> Which real role that maps to is still TODO — see *Decision-maker* above.

### App layout established

The assumptions → model → scenarios → decision skeleton wasn't fixed yet in v0 (v0 had
no scenarios at all — that's v1). What v0 did fix, and what survived every later
version unchanged, was the separation itself: a file-based pipeline where every stage
reads files and writes files, nothing in-memory-coupled, every intermediate artifact
human-readable JSON you can open and argue with (`data/raw/*.json`,
`data/processed/*.json`). That discipline is why scenarios (v1) and the live widget
editor (this submission) could both be added later without touching the acquire,
features, or model stages at all.

### Model: nearest-branch assignment + a three-signal rubric

Every community's female population is assigned wholly to its geometrically nearest
branch (haversine distance, no travel time, no habit, no price) — a real, stated-false
assumption, kept because straight-line distance is free and anything better (drive-time
isochrones, a gravity/Huff model) is explicit future work, not yet done (see *v2*
below). Each branch then gets a composite score from three network-normalized
signals — population served, contested catchment share, rating — ranked, top third
PROTECT / bottom third SHRINK / rest HOLD. See *Worked example* below for the exact
arithmetic on three real branches.

**What v0 got right.** A working, zero-API-key, zero-network path from seed CSVs to a
displayed decision in under a day, with every estimated value flagged (not silently
imputed) — the honesty discipline that's held through every later version.

**What v0 got wrong.** Six real gaps, each recorded in `docs/designs/v0.md`'s "Scope
decisions made during the build" rather than papered over: live-data enrichment was
designed but never implemented (raises `NotImplementedError` deliberately, falls back
to seed); a contested-catchment formula was backwards in the original plan (`else
True` instead of `else second_km == 0` for the zero-distance edge case) and had to be
fixed; price research found genuinely zero real per-branch prices anywhere, not just
hard-to-find ones, forcing a single network-wide fallback constant; a stale,
conflicting `DecisionModel` Protocol definition had to be removed; and a UI bug let the
side panel permanently block the layer toggles (moot now — the Streamlit rebuild
replaced that UI entirely, see *Submission pass* below).

**What it proved / disproved about the framing.** Proved: a crude model is still
useful if every assumption and every estimate is visible, and the resulting PROTECT/
HOLD/SHRINK split is specific enough to argue with (city-walk's 393,658-person
catchment vs. nad-al-sheba's 3,229, for instance, aren't close). Disproved nothing
fatal, but exposed that a one-shot report invites exactly one question — "what if
that's wrong?" — that v0 had no way to answer. That's what v1 is for.

## v1 — the feedback loop

**Goal.** Make assumptions editable and recomputable, so the tool can answer "what
would have to be true for this to change?"

### Recompute on changed assumptions

`data/scenarios/baseline.yaml` formalizes what used to be scattered `Settings`
defaults into one explicit, versioned file — "reality," computed once by `just all`
and never touched by a scenario run. A scenario (`data/scenarios/<name>.yaml`) loads
that same fixed baseline raw data into memory, applies overrides, and recomputes
features + model fresh — in this submission's rebuild, entirely without touching disk
(`run_scenario()` in `src/scenario/run.py`), so the live widget editor can run as many
scenarios as a user tries without ever writing to `data/processed/current/`. The CLI
path (`just scenario <file>.yaml`) still writes that directory, for anyone who wants
the artifact on disk. "Do nothing" — the baseline itself — is always the explicit
comparison; there's no way to see a scenario's diff without baseline sitting right
next to it.

### Scenarios

A scenario supports both assumption overrides (`contest_ratio`, decision backend) and
structural changes: patch an existing branch's rating/price/location, or supply a new
id to introduce a hypothetical branch (`data/scenarios/example-perturbations.yaml`
demonstrates all three in one file — relocating `al-safa-2`, re-rating
`jumeirah-park`, and adding a new hypothetical Dubai Marina branch). Community-level
overrides (e.g. a different population estimate) are supported too, lower priority in
the live UI.

### Guarding against the obvious abuse

Not implemented. An override panel invites exactly the failure mode you'd expect — a
user sliding assumptions until the model says what they want it to say — and this
submission doesn't yet report how far an assumption has to move from its baseline
value before a recommendation flips, which is the actual answer to "is this robust or
is it fragile." What *does* exist is the raw material for that: see *Assumptions
register* below, where I ran the actual stress test v0's own design doc proposed
(`contest_ratio` at 1.1 and 1.5 against baseline 1.25) and recorded exactly how many
branches flip at each value. Turning that into an automatic "flips at ±X%" readout per
assumption is the natural next step and isn't done.

**What v1 got right.** The baseline/scenario split itself — baseline provably never
changes as a side effect of exploring a scenario (there's a direct regression test for
this, `test_scenario_run_never_modifies_baseline_dir`), which matters more than it
sounds: a tool whose "reality" can silently drift based on what a user was just trying
out would be worse than no tool.

**What v1 got wrong.** Acquire-stage assumptions (`global_female_share`,
`fallback_price_aed`) aren't perturbable per-scenario — they're baked into
`data/raw/*.json` once, at baseline time, since scenarios never rerun acquire. If what
you actually want to explore is "what if our female-share estimate were different,"
today's mechanism is overriding the resulting population number directly on the
communities you care about, not re-deriving it from a different global share. A real
gap, recorded as deferred rather than silently absent.

## v2 — refining the model

**Not started.** This submission ships with v1's model — the three-signal rubric
described above — unchanged. No alternatives-considered comparison was done, no
gravity/Huff model was built, and the table below is genuinely empty rather than
retrofitted. I'm leaving the section in rather than deleting it because the gap is
real and worth naming explicitly: the single biggest thing a v2 pass would need to
fix is nearest-branch winner-take-all assignment (see *v0*'s model section and
*Signals* below), and a Huff-style gravity model — splitting a community's demand
across *every* branch in proportion to attractiveness over distance, rather than
handing it entirely to the nearest one — is the standard answer in the literature for
exactly this problem.

### Alternatives considered

TODO — not yet done.

| Approach | What it assumes | Why considered | Why chosen / rejected |
|---|---|---|---|
| Nearest branch (Voronoi) | *(what's actually implemented today)* | Free, zero extra data, already built | Chosen for v0/v1 for exactly those reasons; known to be false (see *out of scope*) |
| Fixed-radius catchment | TODO | TODO | TODO |
| Drive-time isochrones | TODO | TODO | TODO |
| Huff gravity model | TODO | TODO | TODO |

### Chosen model

TODO — not yet done; see above.

### How the recommendation is derived

Unchanged from v1/v0 — see *v0*'s model section. No v2 classification logic exists to
describe here yet.

**What v2 got right / wrong.** N/A — not started.

**Still wrong after v2.** Everything listed under *Explicitly out of scope* above,
since v2 hasn't happened. The most consequential: no competitor data, winner-take-all
demand assignment, and no capital/revenue signal of any kind.

## Submission pass — tying it together

This pass replaced the original FastAPI + Leaflet + Netlify demo with a native
Streamlit app (`streamlit_app.py`, `src/webapp/`) — deleted the old stack entirely
rather than leave it dormant, since maintaining two UIs serving the same decisions.json
would have been pure cost. I want to be precise about what this pass actually is,
because it's more than pure packaging: the live, widget-based scenario editor
(`src/webapp/scenario_editor.py`) is new *interaction* capability — v1.md itself named
"an interactive UI for authoring overrides" as explicit deferred future work, and
that's what got built here. What it is **not** is new *modeling* capability: the
rubric/LLM scoring logic in `src/model/` and the assignment logic in `src/features/`
are byte-for-byte unchanged from v1. A reviewer shouldn't have to guess which parts are
new findings (none — the model is identical) and which are new packaging/interaction
(the whole UI layer).

Also in this pass: the app self-heals a missing baseline from committed seed data on
first load (so a fresh deploy — including Streamlit Community Cloud, which clones the
repo fresh — doesn't need anyone to run `just all` first); the decision backend
defaults to rubric everywhere in the live UI, with the LLM option hidden entirely
unless `ANTHROPIC_API_KEY` is configured (cost control — a public deploy with a key set
would otherwise let any visitor trigger paid API calls); and the three pages are
ordered Product → Model → Story specifically to front-load the recommendation for a
consulting audience trained to expect the conclusion before the methodology. One
production bug surfaced and got fixed after deploying: a pydeck serialization quirk
(a bare string keyword argument gets treated as a per-row data accessor unless
quote-wrapped) made every map marker render roughly 2000x too large, alpha-compositing
into a single solid color — see the *Decisions and trade-offs* register below.

---

# Reference

## Business context

- **Network.** 23 branches UAE-wide; 9 of those are in Dubai, which is all this model
  sees. TODO — when founded, staff count per branch.
- **Ownership and who the analysis is for.** TODO — this determines whether the right
  framing is a PE-style capital question or an operator's operational one, and it's
  the same unknown as *Decision-maker* above.
- **Positioning.** Beauty/salon chain; price tier unclear — no real per-branch price
  was findable anywhere (see *Data sources*), and the one data point that exists (a
  chain-wide "Blow Dry for AED 99" promo) is a promotional price, not a tier signal.
  TODO: mall vs. street frontage per branch.
- **Competitive set.** TODO — undefined, because no competitor data exists at all
  (the single biggest omission, per *out of scope* above). "Everyone with 'salon' in
  the name nearby" would not be a real competitive-set definition; this needs actual
  work, not a guess.
- **Market context.** Dubai retail leans mall-dominated and the population is
  heavily expatriate/transient, both of which plausibly affect demand stability and
  habit-driven branch choice in ways this model can't see (it has no habit/loyalty
  signal). TODO: anything more specific than this general framing.

## Data sources

| Source | What it provides | Coverage | Freshness | Licence / terms | Rate limits | Fallback if unavailable | Used? |
|---|---|---|---|---|---|---|---|
| 2GIS UAE branch-aggregation page | Branch name, lat/lng, area, rating, review count | 9 of Bedashing's 23 UAE branches are in Dubai | TODO (checked once, not re-verified since) | TODO | TODO | n/a — seed CSV committed, this is the only branch source | Yes |
| DSC 2022/2024 Population Bulletin (via a Wikipedia mirror) | Community population totals | 50 real Dubai communities | 2022/2024 bulletin | TODO | n/a (static mirror) | n/a — seed CSV committed | Yes |
| `dubaipulse.gov.ae` / `dsc.gov.ae` (direct) | Would have provided per-community gender split | N/A — blocked | N/A | TODO | Blocked by Akamai/Imperva WAF for automated access | Global 49% female-share estimate applied uniformly | **No — rejected, blocked.** Confirmed the underlying bulletin PDF (via Wayback Machine) doesn't publish per-community gender split at all, only emirate-wide — this isn't a scraping failure, the data isn't published at this granularity anywhere checked. |
| Fresha (branch pages) | Would have provided per-branch service pricing | N/A — zero prices found | Checked 3 times, last with a real browser (Playwright) rendering pages directly | TODO | TODO | AED 99 fallback constant (one real chain-wide promo price, flagged estimated on every branch) | **No — rejected, no data.** Bedashing has no partnered/claimed listing on Fresha anywhere; pages found are unclaimed "discovery" pages with service names and zero attached prices. |
| Groupon / Cobone, social media | Would have provided per-branch pricing or promos | N/A | Checked once | TODO | TODO | Same AED 99 fallback | No — nothing found |

**Provenance in the app.** Every value derived from an estimate rather than a measured
source carries an `estimated_fields` flag in `branch_features.json`, surfaced in the
Model page's data-provenance section; today that's `avg_price_aed` (100% of branches)
and `female_pop_served` (100% of communities, since every community's gender split is
estimated).

## Signals: what we want vs. what we have

| What we'd want | Best available proxy | Gap / bias introduced | Effect on the recommendation |
|---|---|---|---|
| Branch revenue | Nothing | No demand-side performance signal at all | SHRINK can't distinguish a badly-located branch from a well-located, badly-run one |
| Footfall | Nothing | Population served is a catchment-size proxy, not an observed behavior | Assumes population = demand, ignoring habit, convenience, parking |
| Catchment demand | Female population, straight-line nearest-branch assignment | Ignores travel time, malls, parking, price, brand loyalty; winner-take-all at community boundaries | A community right on a boundary is entirely assigned to whichever branch is geometrically closer, even by meters |
| Branch quality | 2GIS star rating + review count | A rating is a coarse, review-selection-biased proxy for actual service quality | Rating is 1/3 of the composite score — review-bombing or review-farming would directly move a branch's tier |
| Competitive position | Nothing | The single biggest omission | A branch with five rival salons next door scores identically to one with none |
| Cost of occupancy | Nothing | No lease/rent data | SHRINK can't tell an expensive underperforming lease from a cheap quiet one |
| Invested capital | Nothing | No capex/fit-out data | No ROIC-style objective is computable — this is the direct cause of the *Objective function* gap above |

## Assumptions register

| Assumption | Default | Basis | Plausible range | Recommendation sensitive to it? |
|---|---|---|---|---|
| `contest_ratio` | 1.25 | Heuristic threshold for "second-nearest branch close enough to count as contested" — not derived from data or literature; v0's own design doc names it "a threshold nobody justified" | 1.1 – 1.5 (actually tested, not guessed) | **Yes — confirmed.** At 1.1: 2 of 9 branches flip action (al-warqa PROTECT→HOLD, palm-jumeirah HOLD→PROTECT). At 1.5: 4 of 9 flip (city-walk PROTECT→HOLD, mirdif-35 HOLD→SHRINK, nad-al-sheba SHRINK→HOLD, palm-jumeirah HOLD→PROTECT). An unjustified threshold swings nearly half the network. |
| `global_female_share` | 0.49 | Rough UAE/Dubai demographic estimate, applied uniformly since the real per-community split isn't published anywhere checked (see *Data sources*) | TODO — not stress-tested; it's an acquire-stage assumption, baked into `data/raw/*.json` once, and isn't perturbable per-scenario in this version (see *v1*'s "got wrong") | TODO |
| `fallback_price_aed` | 99.0 AED | The single real Bedashing price point found anywhere (a chain-wide "Blow Dry for AED 99" promo), applied to every branch since none has a real recorded price | n/a — no real alternative price exists to range over | **No.** The rubric's composite score uses only population served, contested share, and rating — price contributes to a computed `price_index` field that the current decision model doesn't actually read. |
| Decision backend | `llm` (baseline), `rubric` (default in the live scenario editor) | `llm` picked for the original baseline per v0's design (richer per-branch reasoning); `rubric` made the live-editor default because its cache can't help across different scenarios anyway, and it's free, instant, and deterministic | `rubric` or `llm` | **Yes.** Different backends can reach different conclusions on identical inputs; the app surfaces an explicit warning when baseline and a scenario were decided by different backends, so a flip isn't silently misattributed to the override alone. |

## Worked example

Three real branches from the current baseline (rubric backend), composite score =
average of three network-normalized signals (population served, inverted contested
share, rating), ranked network-wide: top 3 of 9 → PROTECT, bottom 3 → SHRINK, middle 3
→ HOLD. Network ranges at the time of this baseline: population served 3,229–393,658;
contested share 0.0–1.0; rating 4.6–4.9.

**Branch: jumeirah-park (PROTECT, rank 1 of 9)**
1. Catchment and demand — 225,283 female population served, entirely uncontested
   (`contested_share = 0.0`): no neighboring branch is close enough, by `contest_ratio`,
   to be competing for the same communities.
2. Capture share — n/a at this stage; nearest-branch assignment means jumeirah-park
   captures 100% of every community assigned to it, by construction.
3. Normalized scores — population: (225,283 − 3,229) / (393,658 − 3,229) = **0.569**.
   Contest: 1 − (0.0 − 0.0)/(1.0 − 0.0) = **1.000**. Rating: (4.8 − 4.6)/(4.9 − 4.6) =
   **0.667** (rating 4.8).
4. Composite — (0.569 + 1.000 + 0.667) / 3 = **0.745**.
5. Rank — 1st of 9 (top third) → **PROTECT**. Matches the app's actual output exactly.

**Branch: al-barsha-2 (HOLD, rank 6 of 9 — the closest call to a tier boundary)**
1. Catchment and demand — 42,648 female population served, `contested_share = 0.334`
   (moderately contested).
2. Normalized scores — population: (42,648 − 3,229)/390,429 = **0.101**. Contest:
   1 − 0.334 = **0.666**. Rating: (4.7 − 4.6)/0.3 = **0.333** (rating 4.7).
3. Composite — (0.101 + 0.666 + 0.333) / 3 = **0.367**.
4. Rank — 6th of 9, inside the middle third → **HOLD**. The branch immediately above it
   (palm-jumeirah, rank 4, composite 0.463) and immediately below (mirdif-35, rank 5,
   composite 0.396) are both close enough that a small assumption change moves the
   tier boundary across one of these three — this is exactly the kind of call the
   *Assumptions register*'s sensitivity test above was checking for.
5. Resulting recommendation — HOLD, no specific action; the genuinely interesting
   finding is how close this one sits to flipping either way.

**Branch: al-safa-2 (SHRINK, rank 9 of 9 — lowest in the network)**
1. Catchment and demand — only 35,133 female population served, and heavily
   contested (`contested_share = 0.874`) — most of its nominal catchment is closer to
   a rival branch under the current `contest_ratio`.
2. Normalized scores — population: (35,133 − 3,229)/390,429 = **0.082**. Contest:
   1 − 0.874 = **0.126**. Rating: (4.6 − 4.6)/0.3 = **0.000** (rating 4.6, tied with the
   network floor).
3. Composite — (0.082 + 0.126 + 0.000) / 3 = **0.069** — the lowest score in the
   network.
4. Rank — 9th of 9 (bottom third) → **SHRINK**. Matches the app's actual output exactly.
5. What this recommendation can't tell you — whether al-safa-2 is badly *located* (low
   catchment, high overlap with a rival) or badly *run*; there's no revenue or
   footfall signal to distinguish the two (see *Signals* above).

## Decisions and trade-offs

| Decision | Alternative rejected | Reason | When | Revisit if |
|---|---|---|---|---|
| Nearest-branch (winner-take-all) demand assignment | Drive-time isochrones, Huff gravity model | Free, zero extra data, buildable in a day; known false, named explicitly as v2 future work | v0 | A v2 pass gets scheduled (see *v2* above) |
| Contested-catchment edge case: `else second_km == 0`, not `else True` | The original (wrong) formula | As `nearest_km → 0`, `second_km/nearest_km → ∞`, which is never `< contest_ratio` — the original formula had this backwards | v0, caught in review | n/a — fixed |
| Single network-wide fallback price (AED 99) for every branch | Per-branch price research | Checked three times across four sources (2GIS, Fresha w/ real browser, Groupon/Cobone, social media); genuinely zero real per-branch prices exist, not just unsourced ones | v0 | A real pricing data source becomes available |
| Baseline never auto-promoted from a scenario run | Letting a scenario become the new baseline | Baseline must only change by a deliberate, explicit re-run against new source data — never as a side effect of exploring a hypothetical | v1 | n/a — load-bearing invariant, has a direct regression test |
| Acquire not rerun per scenario | Making `global_female_share`/`fallback_price_aed` perturbable per-scenario | Those assumptions only affect acquire-stage imputation, baked into `data/raw/*.json` once; rerunning acquire per scenario was out of scope for v1 | v1 | Rerunning acquire per scenario gets built |
| Rubric as the live scenario editor's default backend | LLM as default | LLM's disk cache never helps across *different* scenarios (only repeated runs of the same one) — every scenario costs a real API call with no reuse benefit | v1 / submission pass | n/a |
| `llm` backend option hidden unless `ANTHROPIC_API_KEY` is configured | Always offering both options | A public deploy with a key set would otherwise let any visitor trigger paid API calls on arbitrary scenarios | Submission pass | n/a — deliberate cost control |
| Deleted the old FastAPI + Leaflet + Netlify stack outright | Keeping it dormant alongside the new Streamlit app | Maintaining two UIs reading the same `decisions.json` is pure ongoing cost for zero benefit once Streamlit replaced it | Submission pass | n/a |
| `st.pydeck_chart` over `streamlit-folium` for the map | `streamlit-folium` (closer to the old Leaflet-based UI) | `pydeck` ships bundled with Streamlit (no added dependency) and its `on_select` integrates more idiomatically with Streamlit's rerun model | Submission pass | A pydeck limitation is found that folium wouldn't have had — see the row immediately below, which is exactly that |
| App self-heals a missing baseline on first load instead of requiring `just all` first | Documenting "run `just all` first" and leaving it at that | A fresh Streamlit Community Cloud deploy clones the repo fresh; nothing would otherwise run the pipeline, and the app would crash on first load | Submission pass | n/a |
| Fixed a pydeck serialization bug (`radius_units="pixels"` silently became a broken per-row accessor expression, making every marker render ~2000x too large) | Switching away from pydeck entirely | Root-caused precisely (pydeck quote-wraps literal string kwargs, bare strings become accessor expressions); a one-line, well-tested fix, not a reason to abandon the library choice above | Submission pass, after deploying and finding the map rendered as a solid color | n/a — fixed, with a regression test asserting the serialized spec, not just the row data |

## Where to trust this, and where not

**Trust it for:** a first-pass screen across an existing branch network using signals
that genuinely exist (location, 2GIS rating, population) — and specifically for
surfacing *which* branches are closest to a tier boundary (see al-barsha-2 in the
*Worked example*) and *how fragile* a given split is to an unexamined threshold (see
the `contest_ratio` sensitivity test in the *Assumptions register*).

**Do not trust it for:** any decision that needs to weigh actual commercial
performance, competitive intensity, or capital cost — none of those signals exist in
this pipeline (see *Signals* above). Don't treat a SHRINK label as "this branch is
failing"; it only means "this branch ranks low on population, contested-catchment
share, and rating, relative to its 8 siblings this month."

**Objections and answers**

- *"Why should I believe this number?"* — Every derived figure traces to either a
  named real source (2GIS, DSC) or an explicitly flagged estimate (`estimated_fields`
  in the data, rendered with a provenance note on the Model page). Nothing is silently
  imputed.
- *"This contradicts what I know about branch X."* — Likely true, and expected: the
  model has no competitor, revenue, or footfall signal, so local knowledge you have
  that isn't in those three input signals will outrank it. That's a reason to override
  the specific signal you disagree with (via a scenario) and see what changes, not a
  reason to distrust the whole model.
- *"What if the ratings are gamed?"* — Plausible and unguarded against; rating is 1/3
  of the composite score with no outlier/fraud detection on review volume or velocity.
- *"What happens when a new competitor opens?"* — Nothing, by construction — there is
  no competitor signal at all, so a new rival opening next to a PROTECT branch would
  not move that branch's tier until/unless someone notices and overrides
  `contest_ratio` or the branch's own catchment manually.

**What would materially improve it.** Ranked by impact: (1) any real revenue or
footfall signal — this alone would let the objective function become an actual
capital-allocation question instead of a population/rating/overlap proxy; (2)
competitor location data — the single biggest named omission since v0; (3) lease-cost
and lease-expiry dates per branch — this is what would make the *Decisions in scope*
table's "capital at stake" column fillable at all.

## Demo

Live app: **https://2pz-ai-case-study-wr7zdmdumqywtp8bvpmbxm.streamlit.app/**

> _Fill:_ a recorded walkthrough leading with the recommendation (not a feature tour)
> — TODO, not yet recorded.

## Repo layout

```
2pz-ai-case-study/
  justfile                    # all / app / scenario / clean / test
  pyproject.toml / uv.lock
  requirements.txt            # for Streamlit Community Cloud's resolver
  streamlit_app.py            # entrypoint: st.navigation() over the 3 pages
  .streamlit/
    config.toml
    secrets.toml.example      # copy to secrets.toml (gitignored) for ANTHROPIC_API_KEY
  data/
    seed/                     # committed -- the guaranteed, zero-network path
    scenarios/                # baseline.yaml ("reality") + hand-edited scenario YAMLs
    raw/, processed/          # gitignored, written by acquire/features/model/scenario
  src/
    config.py                 # pydantic-settings Settings
    models.py                 # pydantic models for every stage boundary
    acquire/                  # seed -> data/raw/*.json
    features/                 # nearest-branch assignment, per-branch features
    model/                    # rubric.py (deterministic), llm.py, run.py (backend select)
    scenario/                 # apply overrides, run in-memory, diff vs. baseline
    webapp/
      data.py                 # baseline loader (self-heals if missing)
      map.py                  # pydeck layer builders
      scenario_editor.py      # widget-based scenario authoring
      pages/                  # product.py (1), model.py (2), story.py (3)
  tests/                       # mirrors src/, one test dir per stage
  docs/
    designs/v0.md, v1.md       # full build history for each version
    superpowers/specs/, plans/ # this submission pass's design + implementation plan
```

> _Fill:_ if you want to point a reviewer at a specific reading order beyond what's
> above, name it here — e.g. `docs/designs/v0.md` → `v1.md` → `src/model/rubric.py` →
> `src/webapp/pages/product.py`.

## Running the pipeline stages separately

```bash
just all                                       # acquire -> features -> model (baseline)
just scenario data/scenarios/example-perturbations.yaml   # run one scenario, write diff.json
just app                                       # the Streamlit app
just test                                      # full test suite
just clean                                     # wipe data/raw, data/processed (never seed/scenarios)
```

Each stage also runs standalone, reading/writing its own stage boundary files, for
opening an intermediate artifact without re-running everything upstream:

```bash
uv run python -m src.acquire.run        # writes data/raw/*.json
uv run python -m src.features.build     # reads data/raw/, writes data/processed/baseline/
MODEL_BACKEND=rubric uv run python -m src.model.run   # reads features, writes decisions.json
```
