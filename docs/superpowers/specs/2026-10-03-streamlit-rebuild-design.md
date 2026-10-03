# Streamlit rebuild — design

Date: 2026-10-03. Status: approved, pending implementation plan.

## Why

This project is a submission to a private equity firm for a technical
analyst / implementer role. The audience is consultants: time-constrained,
skeptical by training, and trained on the pyramid principle — state the
recommendation first, let evidence and methodology follow on request. The
current deliverable (a FastAPI + Leaflet app frozen into a static Netlify
snapshot) fails that audience on two counts: it can't be perturbed live
(the whole point of this codebase, per `docs/designs/v1.md`), and it has
no narrative — a reviewer lands on a map with no stated conclusion and no
explanation of why this exists or who built it with what reasoning.

This design replaces the FastAPI/Leaflet/Netlify stack with a Streamlit
app that (a) actually supports live perturbation by importing the
pipeline modules in-process instead of talking to a frozen JSON snapshot,
and (b) is structured the way a consulting deliverable is structured:
conclusion, then evidence, then methodology/appendix, then — last —
the reflective "why I approached it this way" narrative.

## Scope

**Deleted entirely:** `src/serve/` (FastAPI app + static HTML/JS/CSS),
`scripts/build_static_demo.py`, `static-site/`, `netlify.toml`,
`.netlify/`, `tests/serve/`. Drop `fastapi`, `uvicorn[standard]`, `httpx`
from `pyproject.toml` — confirmed nothing outside this set imports them.

**Untouched** (v1.md's own principle: Streamlit is orchestration around
these, not a reason to touch them): `src/acquire/`, `src/features/`,
`src/model/`, `src/models.py`, `src/scenario/apply.py`,
`src/scenario/baseline.py`, `src/scenario/diff.py`, `src/scenario/load.py`,
`src/scenario/models.py`.

**One real refactor:** `src/scenario/run.py`'s `main()` currently couples
"load a scenario from a YAML path" with "run the pipeline and write
results to disk." Split out:

```python
def run_scenario(scenario: Scenario, settings: Settings) -> ScenarioRun:
    """Apply overrides, recompute features+model, diff vs baseline. No disk I/O."""
```

returning a bundle of `features`, `network`, `assignments`, `decisions`,
and `diff` (a new `ScenarioRun` dataclass/pydantic model). `main(path)`
becomes: `load_scenario(path)` → `run_scenario(...)` → write the same
files to `data/processed/current/` as today, so `just scenario <file>`
is behaviorally unchanged. Streamlit builds a `Scenario` object directly
from widget state and calls `run_scenario()` in memory — no temp YAML,
no disk writes, which is what makes "perturb and rerun" actually live.

## Repo layout

```
streamlit_app.py            # entrypoint: st.navigation() over the 3 pages
src/webapp/
  data.py                   # load_baseline(settings) -> typed bundle (replaces
                             # src/serve/app.py's per-route _load/join logic)
  map.py                    # st.pydeck_chart layer builders: branch/community
                             # ScatterplotLayers, assignment/sibling/relocation
                             # LineLayers, diff-highlight rings
  scenario_editor.py        # renders override widgets, returns an in-memory Scenario
  pages/
    product.py               # Page 1
    model.py                 # Page 2
    story.py                 # Page 3
```

## Map: `st.pydeck_chart`, not `streamlit-folium`

`streamlit-folium` is a popular third-party component, not the canonical
Streamlit mapping tool. `st.pydeck_chart` is first-party (ships bundled
with Streamlit — zero added dependency), and its `on_select="rerun"`
support returns a click into Python idiomatically, fitting Streamlit's
rerun model better than parsing folium's return value. No Mapbox token
needed (CARTO-free basemap style, matching v0's "no token" principle).
Tradeoff: plainer tooltips than folium's full HTML popups — irrelevant
here since the feature/decision detail panel is separate Streamlit
widgets next to the map, not an in-map popup.

Layers needed, matching the current JS frontend's visual language:
- `ScatterplotLayer` for branches: radius ∝ `sqrt(female_pop_served)`,
  color by `action` (PROTECT/HOLD/SHRINK), click-selectable.
- `ScatterplotLayer` for communities (toggleable): radius fixed small,
  opacity ∝ `female_pop`, color inherited from assigned branch's action.
- `LineLayer` for community→nearest-branch assignment lines (toggleable).
- `LineLayer` for sibling-branch proximity lines (shown on branch select,
  branches within 5km).
- Diff mode (once a scenario has run): dashed-ring equivalent for
  flipped/changed branches, relocation lines (old→new position), new
  dashed markers for scenario-introduced branches, rings for reassigned
  communities.

## Page order: Product → Model → Story

Reversed from the originally-presented Story → Model → Product order,
to match the pyramid principle a consulting audience reads by: state the
conclusion, then let the reader descend into supporting evidence and
methodology on their own initiative, with the reflective "why I built it
this way" narrative last as the most optional layer.

### Page 1 — "The Product" (lead with the recommendation)

Two parts, top to bottom:

1. **Headline block**, computed live from `data/processed/baseline/decisions.json`
   (never hardcoded copy — a hardcoded headline goes silently stale if the
   pipeline is rerun against different data, which cuts against this
   project's own "don't silently estimate" discipline). States the
   recommendation pattern categorically: counts of PROTECT/HOLD/SHRINK,
   the dominant drivers behind the SHRINK calls (e.g. contested share,
   underpricing), and one line on confidence/caveats. No named
   single-branch example for now — deliberately deferred until there's
   feedback on the document to react to. No firm-specific framing in the
   copy (the role's scope was left open-ended) — the headline is strictly
   about Bedashing's result.
2. **The live demo**: provenance header (backend, data sources, pipeline
   run timestamp) + the pydeck map + a selected-branch detail panel
   (features vs. network medians, decision, rationale, key drivers,
   caveats) + the widget-based scenario editor (override an existing
   branch's rating/price/location, or add a hypothetical new branch;
   assumption sliders for `contest_ratio` and rubric/LLM backend, rubric
   default per v1.md's own recommendation) + a "Run scenario" button that
   calls `run_scenario()` in memory and re-renders the map with diff
   highlights. "Reset to baseline" clears the session scenario. This
   section is framed in-copy as "the evidence — stress-test the
   assumptions yourself," reframing the perturbation feature as
   sensitivity analysis rather than a tech demo.

### Page 2 — "Model, Assumptions & Data" (prove the headline)

The methodology and data-honesty appendix a consultant checks next: the
4-stage pipeline explained, the data-provenance table (ratings real;
**every** price and **every** female-population figure is an estimate —
ported verbatim from `docs/designs/v0.md`'s "What's actually in the seed
data"), the rubric scoring method (normalize, equal-weight sum, top/bottom
third thresholds) vs. the LLM backend (per-branch Claude call, disk-cached,
rubric-fallback-on-failure), and the 8-item known-limitations list
(currently hidden behind a toggle in the JS frontend — made permanent,
visible content here since unpacking it is this page's whole purpose).
If `ANTHROPIC_API_KEY` is configured as a deployed-app secret, optionally
show live rubric-vs-LLM agreement; otherwise the page states plainly that
the public demo runs rubric-only (free, deterministic) by design.

### Page 3 — "Why This Exists" (approach, last)

Static narrative: the business question, who's reading this and why it's
a running pipeline instead of a slide deck, the "perturb, re-run, compare"
philosophy from `v1.md`, and the project's evolution (v0 static prototype
→ v1 scenarios/diffing → this Streamlit version realizing v1's deferred
"interactive override UI" next step). Least load-bearing page for the
pyramid-principle read, most load-bearing for personality/fit signal.

## Testing

- Extend `tests/scenario/test_run.py` to cover `run_scenario()` directly
  (the one real refactor) — same assertions `main()`'s tests already make,
  applied to the function before the disk-write wrapper.
- Add `tests/webapp/test_data.py` for `src/webapp/data.py`'s loader/join
  functions (equivalent coverage to today's `tests/serve/test_app.py`,
  minus the HTTP layer).
- One `streamlit.testing.v1.AppTest` smoke test per page (loads without
  exception, baseline data renders) in `tests/webapp/test_pages.py`.
- Manual browser verification of the full perturbation flow (add/edit a
  branch, run scenario, see diff) before calling this done — `AppTest`
  checks pages don't crash, it doesn't substitute for actually looking at
  the map.

## Deployment

Add `requirements.txt` (generated via `uv export`, since Streamlit
Community Cloud's resolver expects it) alongside the existing
`pyproject.toml`/`uv.lock`. Deploy `streamlit_app.py` from the GitHub repo
to Streamlit Community Cloud. Set `ANTHROPIC_API_KEY` as an app secret
only if the optional page-2 LLM-agreement feature is wanted. README gets
updated run/deploy instructions in place of the Netlify ones.

## Out of scope (deferred, not forgotten)

- Community-level overrides (`population_female`) get a lower-priority
  "Advanced" expander on the scenario editor, not top billing — branch
  rating/price/location is the headline perturbation story.
- No YAML-scenario-file dropdown in the UI — the widget editor is the
  only authoring path in Streamlit; the existing `data/scenarios/*.yaml`
  files remain valid for direct CLI use (`just scenario <file>`),
  unchanged.
- Naming a single illustrative branch in the page-1 headline — deferred
  until there's feedback on the document to react to.
- Firm-specific framing of the headline copy — the role was left
  open-ended; revisit once the two of you go over the document together.
