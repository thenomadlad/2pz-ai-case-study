# Model Refinement (served demand, notebook-first) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the lounge and growth calls on a **served vs. unserved demand** model, worked out and justified in notebooks (assumptions, thresholds, sensitivity, sanity checks), on branch `model-refinement`. The app switches over only after you've reviewed the notebook results.

**Architecture:**
- **Allocation.** Each cell's addressable women are split across every premium supplier (our lounges and premium competitors) that can reach them. The split uses a Huff model: attractiveness (reviews^α) × drive-time decay (by 10/15/20-minute band). Drive times come from the per-cell Mapbox isochrones where we have them, and from a straight-line fallback (fitted in a notebook) elsewhere.
- **Served demand.** A lounge's served demand is the sum of its shares across cells. An optional capacity cap moves any excess to unserved.
- **Unserved demand.** A cell's unserved demand is whatever no supplier serves.
- **What rests on it:**
  - The lounge signals: served women replaces raw catchment women; cannibalisation becomes "demand siblings would absorb", from leave-one-out.
  - The growth rule: GROW means unserved demand, anywhere, including inside our footprint.
- **Where things live.** Logic lives in `src/`. Notebooks import it, explore it and record decisions, which are committed as constants with a WHY. A frozen copy of today's calls (`baseline_v3_labels.csv`) is the reference every notebook compares against.

**Tech Stack:** Python 3.11+, pandas, numpy, shapely (already used by the scripts), Jupyter via `uv run --extra notebook`, pytest. No new dependencies. No paid APIs.

**Spec:** `docs/rubric.md` Part 7 (OB1–OB5, MO4-Huff, MO6, MO8, MO11) and the user's request on 2026-10-11 ("create notebooks for each of our models, with our assumptions and decision thresholds analyzed… dig into and refine the model with notebooks before updating the site"). Also `docs/sanity-checks.md` (its rules and BT1–BT6, SC1–SC7) and the conversation decisions recorded in RUBRIC OB1–OB4:
- the objective is services delivered;
- a lounge is a capacity bundle;
- cannibalisation means shared-zone demand below combined capacity;
- whitespace means unserved demand;
- ratings count as attractiveness, not health.

## Global Constraints

- **Branch:** all work goes on `model-refinement`. Commit small and push often. `main` keeps the v3 model, so the two can run side by side.
- **Data:** `data/seed/v3` plus fresh sources only (no old seed data). Fetching more Mapbox isochrones is allowed only if a notebook shows the straight-line fallback isn't good enough. Report the request count first; the free tier is about 100k a month.
- **Logic in `src/`; notebooks only import.** No model logic is defined inside a notebook.
- **Every model notebook runs in the test suite** (Task 1), so a notebook that no longer matches the code fails.
- **Every new constant** sits next to its logic, with a `*_WHY` string that states the evidence and date.
- **Calibration discipline (rubric MO7).** Each notebook's first cell states the expected outcome before its analysis. Parameters are chosen by criteria written down before looking at the labels. The 24 lounges are both the calibration set and the validation set, so say which check validates which choice.
- **No paid API calls.** Explanations are not regenerated in this plan, because the app switch is a separate, later step.
- **v3 stays the default** in `src.baseline.run()` until the switch step. The v4 code is reached through `run(model="v4")`.

## Review Focus

1. **Cells with no supplier in reach** (desert edges, outer Fujairah). Expect all of their demand to count as unserved, with no division by zero in the Huff denominator. Pinned in Task 3.
2. **A cell reached by a lounge but no competitor.** Expect the lounge to take its full reachable share (subject to the cap), not NaN or 0. Pinned in Task 3.
3. **Closing a lounge (the what-if).** Expect its demand to redistribute to the remaining suppliers or become unserved. Total served plus unserved stays equal to total demand (conservation). Pinned in Task 3.
4. **A cell without a Mapbox isochrone.** Expect the straight-line fallback to be used and flagged in the cell's record, never a silent "unreachable". Pinned in Task 2.
5. **v3 behaviour unchanged on the default path.** Expect `run()` with no model argument to reproduce `baseline_v3_labels.csv` exactly. Pinned in Task 0 and re-checked in every task's test run.

---

### Task 0: Frozen baseline and expected outcomes

**Files:**
- Create: `data/scenarios/baseline_v3_labels.csv` (the output of `just labels` on today's model)
- Modify: `docs/sanity-checks.md` (new section "Expected outcomes for the v4 served-demand model", before `## Run log`)
- Test: `tests/test_baseline_v3.py`

**Interfaces:**
- Produces: `baseline_v3_labels.csv` with the columns `just labels` prints (kind, id, action, …). Every later notebook diffs against it.

- [ ] **Step 1: Freeze the baseline**

```bash
just labels > data/scenarios/baseline_v3_labels.csv
head -3 data/scenarios/baseline_v3_labels.csv
```

- [ ] **Step 2: Write the failing test that v3 still reproduces it**

```python
# append to tests/test_baseline_v3.py
def test_default_run_reproduces_the_frozen_v3_labels():
    import io, subprocess
    import pandas as pd
    from src.config import REPO_ROOT
    frozen = pd.read_csv(REPO_ROOT / "data" / "scenarios" / "baseline_v3_labels.csv")
    now = pd.read_csv(io.StringIO(subprocess.run(["just", "labels"], capture_output=True, text=True,
                                                  cwd=REPO_ROOT, check=True).stdout))
    pd.testing.assert_frame_equal(now, frozen)
```

Run: `uv run --extra dev --extra notebook pytest tests/test_baseline_v3.py -k frozen -v`. Expected: PASS once the file exists. Prove it can fail by editing one action in the CSV, running it, then restoring the file.

- [ ] **Step 3: Write the expected outcomes (before any v4 code)**

```markdown
## Expected outcomes for the v4 served-demand model (written 2026-10-11, before the work)

- **Conservation:** served + unserved = addressable women, in every cell and in total, at every level.
- **SHRINK changes.** The 5 v3 SHRINKs (all Abu Dhabi city lounges, 98–100% overlap) don't all stay SHRINK. If the Abu Dhabi city cells hold more demand than the lounges reaching them can serve, overlap stops being a penalty. Expect 0–3 SHRINK in v4. If all 5 stay, the reason must be that siblings absorb their demand in BT1, not overlap.
- **GROW gains places inside the footprint.** At least one v4 GROW sits inside a lounge's 20-min reach (impossible in v3). GROW stops being only near-empty places: BT5's "0 of 128 GROW cells next to a premium cluster" rises.
- **BT1 becomes runnable.** Closing a PROTECT lounge leaves most of its served demand unserved or with competitors. Closing a SHRINK sends most of it to siblings.
- **BT3 agreement improves:** a lounge's label and the growth label of its own place agree more often than v3's 0 of 3 for PROTECT.
- **PROTECT:** 2–5 lounges. Today's al-ain, al-taif-mall and ras-al-khaimah are isolated markets, so they should stay.
```

- [ ] **Step 4: Commit**

```bash
git add data/scenarios/baseline_v3_labels.csv tests/test_baseline_v3.py docs/sanity-checks.md
git commit -m "Frozen v3 labels and v4 expected outcomes (before the served-demand work)"
git push
```

---

### Task 1: Notebooks run in the test suite

**Files:**
- Create: `tests/test_notebooks.py`
- Modify: `justfile` (recipe `notebooks`)

**Interfaces:**
- Produces: a parametrised test that executes each notebook. It adds about 50 s to `pytest` (measured on 2026-10-10). A slow-marker isn't needed yet; add one if the suite passes 2 minutes.

- [ ] **Step 1: Write the test**

```python
# tests/test_notebooks.py
"""Every notebook must still execute against the current code: a notebook that drifts from src/ fails here."""
import subprocess
from pathlib import Path

import pytest

NOTEBOOKS = sorted((Path(__file__).resolve().parents[1] / "notebooks").glob("*.ipynb"))


@pytest.mark.parametrize("nb", NOTEBOOKS, ids=lambda p: p.stem)
def test_notebook_executes(nb, tmp_path):
    subprocess.run(["jupyter", "nbconvert", "--to", "notebook", "--execute", "--output-dir", str(tmp_path),
                    str(nb)], check=True, capture_output=True)
```

- [ ] **Step 2: Run it**

Run: `uv run --extra dev --extra notebook pytest tests/test_notebooks.py -v`. Expected: 8 PASS (the current notebooks execute; they were re-run on 2026-10-10). To prove it can fail, break one import in a scratch copy, run it, then restore.

- [ ] **Step 3: Add `just notebooks`, then commit**

```make
# Re-execute every notebook in place (outputs committed)
notebooks:
    for nb in notebooks/*.ipynb; do uv run --extra notebook jupyter nbconvert --to notebook --execute --inplace "$nb"; done
```

```bash
git add tests/test_notebooks.py justfile
git commit -m "Notebooks execute in the test suite; just notebooks re-runs them in place"
git push
```

---

### Task 2: Access, i.e. which suppliers each cell reaches, and in how long

**Files:**
- Create: `scripts/build_access.py`
- Create (output): `data/seed/v3/cell_access.csv` with columns `cell_id, place_id, minutes, source` (minutes ∈ {10, 15, 20}; source ∈ {isochrone, straight_line})
- Create: `notebooks/access.ipynb` (fits and justifies the straight-line fallback)
- Test: `tests/scripts/test_access.py`

**Interfaces:**
- Consumes: `cell_isochrones.geojson` (810 cells × 3 bands), `salons.csv` (non-excluded women's salons, plus Bedashing lounges via `is_bedashing`), `cells.csv`.
- Produces:
  - `scripts.build_access.band_from_km(km: float, km_per_band: dict[int, float]) -> int | None`
  - `KM_PER_BAND` (fitted in the notebook) with `KM_PER_BAND_WHY`
  - `cell_access.csv`
  - `src.data_v3.V3.access: pd.DataFrame` (loaded when the file exists, else empty)

- [ ] **Step 1: Write the failing test**

```python
# tests/scripts/test_access.py
from scripts.build_access import band_from_km


def test_band_from_km_is_the_first_band_that_reaches_and_none_beyond():
    km = {10: 6.0, 15: 10.0, 20: 14.0}
    assert band_from_km(2.0, km) == 10
    assert band_from_km(8.0, km) == 15
    assert band_from_km(13.9, km) == 20
    assert band_from_km(14.1, km) is None
```

- [ ] **Step 2: Run it.** Expected: FAIL (module missing).

- [ ] **Step 3: Implement `scripts/build_access.py`**

```python
"""One-off: which salons (and lounges) each populated cell reaches within 20 min, and in which band.

Where the cell has Mapbox isochrones (the 810 cells inside some lounge's 20-min reach;
cell_isochrones.geojson), a salon's band is the first polygon (10/15/20 min) containing it. Elsewhere
the band comes from straight-line distance via KM_PER_BAND, fitted on the isochrone cells in
notebooks/access.ipynb. Output: data/seed/v3/cell_access.csv (cell_id, place_id, minutes, source).

Run: uv run --extra notebook python scripts/build_access.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.features.lounges import haversine_km

V3 = ROOT / "data" / "seed" / "v3"
BANDS = (10, 15, 20)
KM_PER_BAND = {10: 0.0, 15: 0.0, 20: 0.0}   # set in Task 2 Step 5 from notebooks/access.ipynb
KM_PER_BAND_WHY = "Set from notebooks/access.ipynb: see its fit section."


def band_from_km(km: float, km_per_band: dict[int, float]) -> int | None:
    return next((b for b in BANDS if km <= km_per_band[b]), None)


def main() -> None:
    cells = pd.read_csv(V3 / "cells.csv").set_index("cell_id")
    s = pd.read_csv(V3 / "salons.csv")
    s = s[s.excluded_reason.fillna("").eq("")]
    pts = [Point(x, y) for x, y in zip(s.lng, s.lat)]
    tree = STRtree(pts)
    iso = {}
    for f in json.loads((V3 / "cell_isochrones.geojson").read_text())["features"]:
        iso.setdefault(f["properties"]["cell_id"], {})[f["properties"]["minutes"]] = shape(f["geometry"])
    rows = []
    for cid, c in cells.iterrows():
        if cid in iso:
            seen = set()
            for b in BANDS:
                for i in tree.query(iso[cid][b], predicate="contains"):
                    if i not in seen:
                        seen.add(i)
                        rows.append((cid, s.place_id.iloc[i], b, "isochrone"))
        else:
            d = haversine_km(c.lat, c.lng, s.lat.values, s.lng.values)
            for i in np.flatnonzero(d <= KM_PER_BAND[20]):
                rows.append((cid, s.place_id.iloc[i], band_from_km(d[i], KM_PER_BAND), "straight_line"))
    out = pd.DataFrame(rows, columns=["cell_id", "place_id", "minutes", "source"])
    out.to_csv(V3 / "cell_access.csv", index=False)
    print(f"{len(out):,} cell-supplier pairs; {out.cell_id.nunique()} cells; "
          f"{out.source.value_counts().to_dict()}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test.** Expected: PASS.

- [ ] **Step 5: `notebooks/access.ipynb` fits `KM_PER_BAND`**

Cells, in order. Each markdown cell states its finding in numbers.
1. **Expected outcome:** "drive-time bands map onto straight-line distance with ≥ 80% agreement within one band on the 810 isochrone cells; the fitted km thresholds rise with the band".
2. Run `scripts/build_access.py` once with the placeholder `KM_PER_BAND` (zeros): the isochrone rows come out complete and the fallback rows empty. From `cell_access.csv` rows with `source == "isochrone"`, record each pair's true band and its straight-line km.
3. Choose `KM_PER_BAND[b]` as the km that maximises agreement for band b (a grid search at 0.5 km steps), with the 20-min band as the reach limit. Report the agreement and a confusion matrix.
4. **Decision rule, written before cell 3 runs:** accept the fallback if exact-band agreement is ≥ 60% and within-one-band agreement is ≥ 80%. Otherwise report how many more cells need isochrones and the Mapbox request count, then stop and ask before fetching.
5. Write the chosen values and agreement into `KM_PER_BAND` / `KM_PER_BAND_WHY` in `scripts/build_access.py`. Run the script, and paste its printed line into the notebook.

- [ ] **Step 6: Load into V3, then commit**

In `src/data_v3.py`, add `access: pd.DataFrame = field(default_factory=pd.DataFrame)` to `V3`, and in `_load` read `cell_access.csv` when it exists. Run `uv run --extra dev --extra notebook pytest -q`. Expected: green.

```bash
git add scripts/build_access.py tests/scripts/test_access.py notebooks/access.ipynb data/seed/v3/cell_access.csv src/data_v3.py
git commit -m "Cell-to-supplier access bands (isochrones where fetched, fitted straight-line fallback elsewhere)"
git push
```

---

### Task 3: Huff allocation, i.e. served and unserved demand

**Files:**
- Create: `src/model/served.py`
- Test: `tests/model/test_served.py`

**Interfaces:**
- Consumes: `V3.access`, `src.features.lounges` (women and addressable-women helpers as used in `build`), `src.market.premium_substitutes` rule.
- Produces:
  - `src.model.served.HuffParams` (frozen dataclass: `alpha: float`, `decay: dict[int, float]`, `capacity: float | None`)
  - `src.model.served.allocate(demand: dict[str, float], access: pd.DataFrame, attract: dict[str, float], lounges: set[str], params: HuffParams) -> Served`
  - `Served` (dataclass):
    - `by_cell: pd.DataFrame` with columns `cell_id, demand, served_lounges, served_competitors, unserved`
    - `by_lounge: dict[str, float]` (women served, after the cap)
    - `share: pd.DataFrame` with columns `cell_id, place_id, share`

- [ ] **Step 1: Write the failing tests (the Review Focus 1–3 pins)**

```python
# tests/model/test_served.py
import pandas as pd
import pytest

from src.model.served import HuffParams, allocate

P = HuffParams(alpha=1.0, decay={10: 1.0, 15: 0.5, 20: 0.25}, capacity=None)


def _acc(rows):
    return pd.DataFrame(rows, columns=["cell_id", "place_id", "minutes", "source"])


def test_conservation_and_no_supplier_means_all_unserved():
    acc = _acc([("c1", "L", 10, "isochrone"), ("c1", "S", 15, "isochrone")])
    out = allocate({"c1": 1000.0, "c2": 500.0}, acc, {"L": 100.0, "S": 100.0}, {"L"}, P)
    c = out.by_cell.set_index("cell_id")
    assert c.loc["c2"].unserved == 500.0 and c.loc["c2"].served_lounges == 0.0       # nobody reaches c2
    total = c.served_lounges + c.served_competitors + c.unserved
    assert total.tolist() == pytest.approx(c.demand.tolist())                         # conservation
    assert c.loc["c1"].served_lounges == pytest.approx(1000 * 100 / (100 + 100 * 0.5))  # Huff split


def test_lounge_alone_takes_the_whole_cell_and_closing_it_leaves_it_unserved():
    acc = _acc([("c1", "L", 10, "isochrone")])
    out = allocate({"c1": 1000.0}, acc, {"L": 50.0}, {"L"}, P)
    assert out.by_lounge["L"] == pytest.approx(1000.0)
    gone = allocate({"c1": 1000.0}, acc[acc.place_id != "L"], {}, set(), P)
    assert gone.by_cell.unserved.iloc[0] == pytest.approx(1000.0)


def test_capacity_caps_a_lounge_and_the_excess_is_unserved():
    acc = _acc([("c1", "L", 10, "isochrone")])
    out = allocate({"c1": 1000.0}, acc, {"L": 50.0}, {"L"}, HuffParams(1.0, P.decay, capacity=600.0))
    assert out.by_lounge["L"] == pytest.approx(600.0)
    assert out.by_cell.unserved.iloc[0] == pytest.approx(400.0)
```

Note: with no market-share term, Huff gives the whole cell to its suppliers. "Unserved" then arises only from no-reach or the capacity cap. Task 4 decides whether to add an outside option (a constant `outside` attractiveness for "no premium salon / goes elsewhere"). The `HuffParams` interface stays the same either way. If an outside option is added, it becomes a field `outside: float = 0.0`, added in Task 4 with its own test.

- [ ] **Step 2: Run them.** Expected: FAIL (module missing).

- [ ] **Step 3: Implement `src/model/served.py`**

```python
"""Served vs unserved demand: each cell's addressable women split across the premium suppliers that
reach it (Huff: attractiveness ** alpha x decay(drive-time band)), optionally capped per lounge.
Parameters are chosen in notebooks/served_demand.ipynb."""
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class HuffParams:
    alpha: float
    decay: dict[int, float]
    capacity: float | None = None


@dataclass
class Served:
    by_cell: pd.DataFrame
    by_lounge: dict[str, float]
    share: pd.DataFrame


def allocate(demand: dict[str, float], access: pd.DataFrame, attract: dict[str, float],
             lounges: set[str], params: HuffParams) -> Served:
    a = access[access.place_id.isin(attract)].copy()
    a["w"] = [attract[p] ** params.alpha * params.decay[m] for p, m in zip(a.place_id, a.minutes)]
    a["share"] = a.w / a.groupby("cell_id").w.transform("sum")
    a["women"] = a.share * a.cell_id.map(demand).fillna(0.0)
    raw = a[a.place_id.isin(lounges)].groupby("place_id").women.sum()
    scale = {}
    for p, v in raw.items():   # a capped lounge serves at most `capacity`; the rest goes unserved
        scale[p] = min(1.0, params.capacity / v) if params.capacity and v > 0 else 1.0
    a["served"] = a.women * a.place_id.map(scale).fillna(1.0)
    lounge_rows = a.place_id.isin(lounges)
    cells = pd.DataFrame({"cell_id": list(demand), "demand": list(demand.values())}).set_index("cell_id")
    cells["served_lounges"] = a[lounge_rows].groupby("cell_id").served.sum()
    cells["served_competitors"] = a[~lounge_rows].groupby("cell_id").served.sum()
    cells = cells.fillna(0.0)
    cells["unserved"] = cells.demand - cells.served_lounges - cells.served_competitors
    by_lounge = a[lounge_rows].groupby("place_id").served.sum().to_dict()
    return Served(cells.reset_index(), {p: by_lounge.get(p, 0.0) for p in lounges},
                  a[["cell_id", "place_id", "share"]].reset_index(drop=True))
```

- [ ] **Step 4: Run the tests.** Expected: PASS. Then the full suite: green (v3 untouched).

- [ ] **Step 5: Commit**

```bash
git add src/model/served.py tests/model/test_served.py
git commit -m "Huff allocation: served and unserved demand per cell and lounge (conserving, capacity-capped)"
git push
```

---

### Task 4: `notebooks/served_demand.ipynb`: choose α, decay, outside option and capacity

**Files:**
- Create: `notebooks/served_demand.ipynb`
- Modify: `src/model/served.py` (chosen constants `ALPHA`, `DECAY`, `OUTSIDE`, `CAPACITY`, each with a `*_WHY`; `outside` field if adopted, with its own test)
- Create: `src/model/served_inputs.py` with `served_for(v3, a, levels, closed) -> Served`. It builds `demand` (addressable women per cell, from the same helpers as `features.lounges.build`), `attract` (lounge and premium-salon reviews; premium per `market.premium_substitutes` over each cell's reachable candidates) and `lounges`, then calls `allocate`.
- Test: `tests/model/test_served.py` (add: `served_for` conserves at baseline on real data; closing a lounge leaves total demand constant)

The notebook's sections. Each starts by restating the decision rule *before* the cell that computes it:
1. **Expected outcome** (copied from Task 0).
2. **Assumptions table:** α, the decay per band, the outside option and capacity. For each: the candidate values, the evidence, and the rule for choosing.
3. **α and decay.**
   - Candidate α ∈ {0.5, 1.0}. Decay is either a fixed geometric series {1, 0.5, 0.25} or fitted.
   - **Rule:** pick the pair whose lounge served shares best match the lounges' own review shares (Spearman ρ over 23 lounges, reported). Prefer the simpler setting unless ρ improves by ≥ 0.1.
   - This is calibration on the lounges, so it's stated as such.
4. **Outside option.** Without one, every reached cell is "fully served", so unserved exists only beyond reach.
   - Candidate: a constant outside attractiveness, equal to the k-th percentile of supplier attractiveness.
   - **Rule:** adopt it if, without it, fewer than 5% of addressable women inside lounge reach are unserved. That would make "unserved" meaningless inside the footprint, which is the point of rubric 2.5.
5. **Capacity.** There's no data, so the options are:
   - (a) none;
   - (b) equal capacity for every lounge, set at the median v3 `est_customers`;
   - (c) proportional to the lounge's own reviews.

   **Rule:** choose the simplest that makes BT1 (leave-one-out) behave as expected for the 3 v3 PROTECTs. Report all three.
6. **BT1 leave-one-out,** for every lounge: close it, re-allocate, and split its served demand into siblings / competitors / unserved. A table, plus the PROTECT-vs-SHRINK comparison against the Task 0 expectation.
7. **Conservation and sanity:** totals per level, and no NaN.
8. **Sensitivity:** how lounge served demand varies across the 81 assumption combinations and the α/decay/capacity candidates.

- [ ] **Steps:** write `served_for` and its test (RED, then GREEN). Build the notebook section by section. Commit the chosen constants with their WHYs. Run `pytest -q` (with Task 1, this includes the notebook). Commit and push.

---

### Task 5: v4 lounge scorecard (`notebooks/scorecard.ipynb`)

**Files:**
- Modify: `src/model/scorecard.py` (add `decide_v4(features, served, flips)`; v3 `decide` untouched)
- Modify: `src/models.py` (`LoungeFeatures` gains `served_women: float | None`, `absorbed_by_siblings: float | None`; defaults None)
- Modify: `src/features/lounges.py` (fill the new fields when `served` is given)
- Modify: `src/baseline.py` (`run(..., model: str = "v3")`; `"v4"` uses `served_for` and `decide_v4`)
- Create: `notebooks/scorecard.ipynb` (split out of `decisions.ipynb`; `decisions.ipynb` keeps v3)
- Test: `tests/model/test_scorecard.py` (v4 signals, anchors, and that `run()` with no argument still equals the frozen v3 labels)

Signal changes, which the notebook justifies:
- **Demand:** `served_women` replaces catchment addressable women. Anchor: the notebook picks it from the v4 distribution, with the same "top of the working range" logic as v3's 200k.
- **Cannibalisation:** `absorbed_by_siblings`, the share of a lounge's served demand that its siblings take over when it closes (from BT1), replaces `shared_share`. This is the "shared-zone demand below combined capacity" definition from RUBRIC 3.6.
- **Capture:** keep it, or drop it if the Huff share makes it redundant. **Rule:** drop it if Spearman ρ(capture, Huff share) ≥ 0.8.
- **Rating:** moves to attractiveness (OB4). It feeds α's attractiveness term, not a health signal. The notebook shows the effect.
- **Thresholds:** the notebook reports the v4 composite distribution and where PROTECT_AT / SHRINK_AT fall. Keep 0.65/0.35 unless the distribution makes one label empty; if they change, record the reason.
- **Diff:** a table against `baseline_v3_labels.csv`. Every label change gets a one-line reason.

- [ ] **Steps:** RED tests for `decide_v4` on fixtures, then GREEN; the notebook; the full suite; commit and push.

---

### Task 6: v4 growth (`notebooks/growth.ipynb`)

**Files:**
- Modify: `src/model/growth.py` (add `classify_v4(area, unserved)`; v3 untouched)
- Modify: `src/features/lounges.py` (an area's `unserved_women` from `Served.by_cell`; areas built over **all** named places, not only unreached cells, in v4)
- Create: `notebooks/growth.ipynb`
- Test: `tests/model/test_growth.py`

What the notebook covers:
- **GROW = unserved addressable women ≥ the size line.** The line is chosen in the notebook (v3's 20k is the starting point), keeping the worker-housing and non-residential rules. The saturation test becomes redundant, because competitors already take their Huff share. **Rule:** drop it if every v3 saturated WATCH area has unserved < the size line in v4.
- **Area confidence includes level flips** (the pass-4 MO6 finding: kalba and al-jerf flip in 27 of 81). Area flips are computed across the 81 combinations in the notebook and in `src` (cached per run).
- **MO11 / BT5 re-check:** the share of GROW cells next to a premium cluster.
- **BT3:** a lounge's label against the growth label of its own place, with the agreement count.
- **Diff** against the frozen v3 labels.

- [ ] **Steps:** RED tests (`classify_v4` on fixtures: an unserved area inside the footprint can be GROW; non-residential stays SKIP), then GREEN; the notebook; the full suite; commit and push.

---

### Task 7: `notebooks/sanity.ipynb` and `just sanity`

**Files:**
- Create: `src/sanity.py` (BT1–BT6 and SC2–SC4 as functions, each returning a small DataFrame plus a pass/explain verdict)
- Create: `notebooks/sanity.ipynb` (runs them for v3 and v4 side by side)
- Modify: `justfile` (`sanity: uv run python -m src.sanity`)
- Modify: `docs/sanity-checks.md` (v4 run results against the Task 0 expectations; run-log row)
- Test: `tests/test_sanity.py` (each check runs, and returns a verdict on both models)

- [ ] **Steps:** port the audit scripts' logic (they live in the session scratch dir and are not in the repo; re-derive from the docs/sanity-checks.md definitions) into `src/sanity.py` behind tests; the notebook; `just sanity`; record the results; commit and push.

---

### Checkpoint: stop for review (no code)

Report to the user:
- The v3 → v4 label diff, with reasons.
- The Task 0 expectations, marked met or not met.
- The chosen parameters and their evidence.
- The sanity results.

**Do not switch the app.** The switch is a separate follow-up plan: make v4 the default, update the app pages, regenerate the explanations offline, update the docs, and run a rubric pass. It starts only after the user approves.

## Out of this plan (next)

- **App switch to v4** (above).
- **ROIC gate (OB5):** contribution = served women × visit frequency × margin per visit − site rent (shop rent × unit m²). It needs visit and margin assumptions sourced, or explicitly marked open. Write a `roic.ipynb` with the assumption table first.
- **Wider OSM naming** for the 67 unnamed cells (data-inventory gap).
