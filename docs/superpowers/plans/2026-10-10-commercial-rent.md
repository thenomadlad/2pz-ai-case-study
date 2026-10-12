# Commercial Rent ("women per rent") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every lounge, lounge catchment and growth area a commercial (shop) rent and a **women per AED 1,000 of annual rent** figure. It is shown next to the existing signals and feeds the ROIC gate's "fixed site cost" assumption later (rubric OB5).

**Architecture:**
- **Dubai** uses DLD Ejari *shop* contracts. They are already downloaded in `data/raw/dld/rents-2026-10-10.csv`: 13,772 single-unit shop contracts, median AED 1,960/m²/yr. They go through the same area → cell pipeline as the residential affluence rents (`scripts/build_affluence.py`).
- **Every other emirate** uses a hand-built table of published retail rent bands (consultancy market reports), one row per emirate × location class. Each lounge is mapped to a class by hand.
- Features compute a women-weighted shop rent per catchment and per area, plus the lounge's own-site rent. The figure is **display only**: it does not enter the scorecard or the growth rule in this plan.

**Tech Stack:** Python 3.11+, pandas, the existing `src/features/lounges.py` feature build, pydantic models, Streamlit pages, pytest. No new dependencies. No paid APIs.

**Spec:** This plan carries its own design: the user's request on 2026-10-10 ("obtain commercial real estate prices for each lounge and ideally each catchment; calculate something like number of women / average dollar of rent"). Read alongside `docs/rubric.md` (OB5, DA1, S6, US7) and `docs/sanity-checks.md` (the rules: expected outcomes before running; no tuning to pass).

## Design decisions (read before Task 1)

1. **The metric.** `women_per_rent_k = addressable_women / (shop_rent_m2 × REF_UNIT_M2 / 1000)`. That is: addressable women in the catchment per AED 1,000 of annual rent for a reference unit of `REF_UNIT_M2` m².
   - We don't know lounge floor areas. `REF_UNIT_M2 = 150` is an **assumption**, marked open in `SOURCES.md`. Because it's one constant for every lounge, it changes the level of the figure but **never the ranking**. Say so wherever it's shown.
2. **Which rent.**
   - **Lounge site rent:** the shop rent of the cell the lounge sits in (Dubai) or its location-class band (elsewhere).
   - **Catchment rent:** the women-weighted median shop rent over catchment cells that have one, plus the share of women covered (same pattern as `affluence_rent` / `affluence_coverage`).
   - **Area rent:** the same over the area's cells.
   - The ratio uses the **site** rent for lounges (what we pay) and the **area** rent for growth areas (what we'd pay there).
3. **Display only, on purpose.** Commercial rent tracks footfall and customer affluence, which is the *revenue* side. A women-per-rent ratio alone would penalise exactly the prime sites a premium salon wants. It also double-counts demand, which the scorecard already scores. Its proper home is the ROIC gate (OB5), as the fixed-site-cost input next to a revenue assumption. That is a separate plan.
4. **Coverage is the main risk, stated up front.**
   - All 5 Dubai lounges are HOLD. All 5 SHRINKs and 2 of 3 PROTECTs are outside Dubai (Abu Dhabi, Ras Al Khaimah).
   - So **Dubai-only data cannot inform any strong call**. Task 3, the non-Dubai bands, is what makes this useful. If Task 3's research finds no citable public source for Abu Dhabi, stop and report back rather than inventing bands.
5. **Residential vs. commercial rent.** These stay separate concepts:
   - Residential rent (`affluence_rent`) stands for *customer affluence* (demand quality).
   - Shop rent (`shop_rent_m2`) is *our cost*.
   - Name and caption them so nobody confuses them.

## Global Constraints

- Data: only `data/seed/v3` plus fresh sources (memory: no old seed data). DLD open data needs no API key.
- No paid API calls. Explanations are regenerated only through the offline path (`justfile` comments: `prompts` → write answers → `check` → `ingest`).
- Work on `main`; commit and push after each task (memory: work on main).
- Every new constant lives next to the logic that uses it, with a `*_WHY` string (rubric MO9).
- Every published-rent row cites a public URL and a publication date. A row without a source is not allowed.
- Labels must not change: this plan adds display fields only. If a label changes, that's a bug.
- Before running, write the run-5 expected outcomes into `docs/sanity-checks.md` (Task 0), as for runs 2 and 3.

## Review Focus

1. **Lounges or areas with no shop rent** (all non-Dubai areas, and Dubai cells beyond 2.5 km of a DLD area). Expect `None` and "no data", never 0, NaN or a division error. Pinned in Task 2.
2. **A single extreme shop contract** (a 3 m² kiosk at AED 80k). Expect contracts under 10 m² and the top and bottom 1% of AED/m² per area to be dropped before the median. Pinned in Task 1.
3. **Confusing shop rent with residential rent.** Expect distinct field names, labels and captions ("Shop rent, AED/m²/yr" vs "Residential rent"). Pinned in Task 4's page test.
4. **The reference unit size read as a fact.** Expect every display of `women_per_rent_k` to say "per AED 1,000 of annual rent for a 150 m² unit (assumed)". Pinned in Task 4.
5. **A lounge in a mall whose cell rent is street-level.** Expect the Dubai figure to carry a caveat that the DLD area median mixes mall and street shops. Pinned in Task 2 (the caveat text) and Task 5 (limitations).

---

### Task 0: Write the expected outcomes (no code)

**Files:**
- Modify: `docs/sanity-checks.md` (new section "Expected outcomes for run 5", before `## Run log`)

- [ ] **Step 1: Add the expectations, before any code exists**

```markdown
## Expected outcomes for run 5 (written before the commercial-rent work)

- **No label changes.** Shop rent is display only. Any change to a lounge or area label is a bug.
- **SC7 (new): plausibility.**
  - Dubai's median shop rent per DLD area lands within published ranges for Dubai community and street retail (roughly AED 1,000–3,500/m²/yr). Prime mall areas (Downtown / Dubai Mall) sit above AED 3,500.
  - Fewer than 10% of located shop areas fall outside AED 300–10,000/m².
- **BT6 (new): women per rent vs. the calls.**
  - Within Dubai all 5 lounges are HOLD, so there's nothing to test.
  - Outside Dubai (after Task 3): no expected direction. PROTECT lounges win on exclusivity and capture, not on cost. Report the ranking, and don't tune anything to it.
- **Coverage.** Dubai shop rent covers most of the 5 Dubai lounge sites. Outside Dubai, coverage is the band table only.
```

- [ ] **Step 2: Commit**

```bash
git add docs/sanity-checks.md
git commit -m "docs/sanity-checks.md: expected outcomes for run 5 (commercial rent), written before the work"
git push origin main
```

---

### Task 1: Dubai shop rent per cell

**Files:**
- Modify: `scripts/build_affluence.py` (make `observed()` take the value column and the minimum contract count)
- Create: `scripts/build_shop_rent.py`
- Create (output): `data/seed/v3/dubai_shop_rents_by_area.csv`, `data/seed/v3/cell_shop_rent.csv`
- Test: `tests/scripts/test_shop_rent.py`

**Interfaces:**
- Consumes: `scripts.build_affluence.locate(areas: DataFrame) -> DataFrame` (adds lat, lng, matched_to, match), `scripts.build_affluence.observed(...)`, `norm()`.
- Produces:
  - `scripts.build_shop_rent.shop_area_rents(rents: DataFrame) -> DataFrame` with columns `area, contracts, median_rent_m2`.
  - The file `cell_shop_rent.csv` with columns `cell_id, shop_rent_m2, assignment` (inside | nearest).

- [ ] **Step 1: Write the failing tests**

```python
# tests/scripts/test_shop_rent.py
import pandas as pd
import pytest

from scripts.build_affluence import observed
from scripts.build_shop_rent import MIN_SHOP_M2, shop_area_rents


def _contract(area, amount, m2, usage="Commercial", sub="Shop", units=1):
    return {"AREA_EN": area, "ANNUAL_AMOUNT": amount, "ACTUAL_AREA": m2, "USAGE_EN": usage,
            "PROP_SUB_TYPE_EN": sub, "TOTAL_PROPERTIES": units}


def test_shop_rent_uses_single_shop_contracts_and_drops_kiosks_and_outliers():
    rows = [_contract("A", 200_000, 100) for _ in range(98)]          # AED 2,000/m2
    rows += [_contract("A", 80_000, 3),                                  # kiosk: under MIN_SHOP_M2
             _contract("A", 9_000_000, 100),                             # top 1%: dropped
             _contract("A", 200_000, 100, sub="Office"),                 # not a shop
             _contract("A", 200_000, 100, usage="Residential"),          # not commercial
             _contract("A", 900_000, 100, units=5)]                      # bulk lease
    got = shop_area_rents(pd.DataFrame(rows)).set_index("area").loc["A"]
    assert got.contracts == 98 and got.median_rent_m2 == pytest.approx(2000)
    assert MIN_SHOP_M2 == 10


def test_observed_takes_any_value_column_and_minimum():
    cells = pd.DataFrame([{"cell_id": "c", "emirate": "Dubai", "lat": 25.01, "lng": 55.01,
                           "south": 25.0, "north": 25.02, "west": 55.0, "east": 55.02}]).set_index("cell_id")
    areas = pd.DataFrame([{"area": "A", "lat": 25.01, "lng": 55.01, "contracts": 12, "median_rent_m2": 1500.0}])
    val, how = observed(cells, areas, col="median_rent_m2", min_contracts=10)
    assert val["c"] == 1500.0 and how["c"] == "inside"
    val, _ = observed(cells, areas, col="median_rent_m2", min_contracts=20)
    assert "c" not in val
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --extra dev --extra notebook pytest tests/scripts/test_shop_rent.py -v`
Expected: FAIL. `scripts.build_shop_rent` doesn't exist, and `observed()` has no `col` parameter.

- [ ] **Step 3: Generalise `observed()` in `scripts/build_affluence.py`**

Replace its signature and the two places that read `median_rent` and `MIN_CONTRACTS`:

```python
def observed(cells: pd.DataFrame, areas: pd.DataFrame, col: str = "median_rent",
             min_contracts: int = MIN_CONTRACTS) -> tuple[pd.Series, pd.Series]:
    """Per Dubai cell: contract-weighted median of `col` over the areas whose point is inside it,
    else the nearest area point within RADIUS_KM. Also how each was assigned (inside | nearest)."""
    a = areas.dropna(subset=["lat"])
    a = a[a.contracts >= min_contracts]
    out, how = {}, {}
    for cid, c in cells[cells.emirate == "Dubai"].iterrows():
        inside = a[(a.lat >= c.south) & (a.lat < c.north) & (a.lng >= c.west) & (a.lng < c.east)]
        if len(inside):
            inside = inside.sort_values(col)
            cum = inside.contracts.cumsum()
            out[cid], how[cid] = float(inside[col][cum >= cum.iloc[-1] / 2].iloc[0]), "inside"
            continue
        d = haversine_km(c.lat, c.lng, a.lat.values, a.lng.values)
        if d.min() <= RADIUS_KM:
            out[cid], how[cid] = float(a[col].iloc[d.argmin()]), "nearest"
    return pd.Series(out, name="rent_observed"), pd.Series(how, name="assignment")
```

`main()` keeps calling `observed(cells, areas)`, so the defaults keep the residential output byte-identical. Verify: `uv run --extra notebook python scripts/build_affluence.py && git diff --stat data/seed/v3/cell_affluence.csv` shows no change.

- [ ] **Step 4: Create `scripts/build_shop_rent.py`**

```python
"""One-off: commercial (shop) rent per ~2 km cell, Dubai only, from DLD Ejari contracts.

Same file and same area -> point -> cell pipeline as the residential rents (scripts/build_affluence.py),
filtered to single-unit commercial shops of MIN_SHOP_M2+ m2, with the top and bottom TRIM of AED/m2
dropped per area. Shop rent is OUR COST (a lounge's site), not customer affluence: keep it apart
from affluence_rent.

Outputs (data/seed/v3/): dubai_shop_rents_by_area.csv, cell_shop_rent.csv
(cell_id, shop_rent_m2, assignment: inside | nearest).

Run: uv run --extra notebook python scripts/build_shop_rent.py
"""
import glob
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.build_affluence import RAW, V3, locate, observed

MIN_SHOP_M2 = 10
MIN_SHOP_CONTRACTS = 10
TRIM = 0.01
WHY = {
    "MIN_SHOP_M2": "Under 10 m2 is a kiosk or counter: its AED/m2 runs several times a shop's.",
    "MIN_SHOP_CONTRACTS": ("Shops are rarer than homes (13.8k vs 251k contracts in 3 months), so an "
                           "area needs 10, not 20, to get a median."),
    "TRIM": "One mistyped contract (an extra zero) moves a small area's median; the 1% tails go.",
}


def shop_area_rents(rents: pd.DataFrame) -> pd.DataFrame:
    """Median AED/m2/yr per DLD area over single-unit shop contracts, tails trimmed."""
    r = rents[(rents.USAGE_EN == "Commercial") & (rents.PROP_SUB_TYPE_EN.str.strip() == "Shop")
              & (rents.TOTAL_PROPERTIES.fillna(1) == 1) & (rents.ANNUAL_AMOUNT > 0)
              & (rents.ACTUAL_AREA >= MIN_SHOP_M2)]
    r = r.assign(m2=r.ANNUAL_AMOUNT / r.ACTUAL_AREA)
    lo, hi = r.m2.quantile(TRIM), r.m2.quantile(1 - TRIM)
    r = r[r.m2.between(lo, hi)]
    return (r.groupby("AREA_EN").agg(contracts=("m2", "size"), median_rent_m2=("m2", "median"))
            .reset_index().rename(columns={"AREA_EN": "area"}))


def main() -> None:
    rents = pd.concat(pd.read_csv(f, encoding="utf-8-sig", low_memory=False)
                      for f in sorted(glob.glob(str(RAW / "dld" / "rents-*.csv"))))
    areas = locate(shop_area_rents(rents))
    areas.to_csv(V3 / "dubai_shop_rents_by_area.csv", index=False)
    cells = pd.read_csv(V3 / "cells.csv").set_index("cell_id")
    val, how = observed(cells, areas, col="median_rent_m2", min_contracts=MIN_SHOP_CONTRACTS)
    out = pd.DataFrame({"shop_rent_m2": val.round(0), "assignment": how})
    out.index.name = "cell_id"
    out.to_csv(V3 / "cell_shop_rent.csv")
    located = areas.match != "unmatched"
    print(f"{located.sum()}/{len(areas)} shop areas located; shop rent for {len(out)} Dubai cells; "
          f"median {out.shop_rent_m2.median():,.0f} AED/m2/yr")


if __name__ == "__main__":
    main()
```

Note on the trim: the plan's test puts one 9,000,000 contract among 98 identical ones, so the 99th percentile cut drops it. Trimming is done over all shops, not per area, which keeps the code to one line. If a reviewer wants per-area trimming, that's a follow-up.

- [ ] **Step 5: Run the tests to verify they pass, then build the data**

Run: `uv run --extra dev --extra notebook pytest tests/scripts/test_shop_rent.py -v` → PASS.
Run: `uv run --extra notebook python scripts/build_shop_rent.py` and paste its printed line into the commit message.

- [ ] **Step 6: Commit**

```bash
git add scripts/build_affluence.py scripts/build_shop_rent.py tests/scripts/test_shop_rent.py \
        data/seed/v3/dubai_shop_rents_by_area.csv data/seed/v3/cell_shop_rent.csv
git commit -m "Dubai shop rent per cell from DLD Ejari shop contracts (<printed summary>)"
git push origin main
```

---

### Task 2: Shop rent and women-per-rent in the features (Dubai)

**Files:**
- Modify: `src/data_v3.py:_cells` (join `cell_shop_rent.csv`; missing file or cell → NaN)
- Modify: `src/models.py` (`LoungeFeatures`, `Area`: new optional fields)
- Modify: `src/features/lounges.py` (a helper plus fields in `build` and `_area`)
- Test: `tests/features/test_lounges.py`

**Interfaces:**
- Consumes: `v3.cells.shop_rent_m2` (float, NaN where none).
- Produces:
  - `LoungeFeatures.site_rent_m2: float | None`
  - `LoungeFeatures.site_rent_source: str` ("dld" | "band" | "none")
  - `LoungeFeatures.catchment_shop_rent_m2: float | None`, `LoungeFeatures.shop_rent_coverage: float`
  - `LoungeFeatures.women_per_rent_k: float | None`
  - `Area.shop_rent_m2: float | None`, `Area.shop_rent_coverage: float`, `Area.women_per_rent_k: float | None`
  - `src.features.lounges.REF_UNIT_M2 = 150` and `REF_UNIT_WHY`
  - `src.features.lounges.women_per_rent_k(women: float, rent_m2: float | None) -> float | None`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/features/test_lounges.py
def test_women_per_rent_is_none_without_rent_and_scales_with_rent():
    from src.features.lounges import REF_UNIT_M2, women_per_rent_k
    assert women_per_rent_k(50_000, None) is None
    assert women_per_rent_k(50_000, float("nan")) is None
    assert women_per_rent_k(50_000, 2000.0) == pytest.approx(50_000 / (2000 * REF_UNIT_M2 / 1000))
    assert women_per_rent_k(50_000, 1000.0) == pytest.approx(2 * women_per_rent_k(50_000, 2000.0))


def test_shop_rent_is_women_weighted_over_cells_that_have_one(tiny_v3):
    tiny_v3.cells["shop_rent_m2"] = float("nan")
    tiny_v3.cells.loc[C1, "shop_rent_m2"] = 1000.0
    tiny_v3.cells.loc[C2, "shop_rent_m2"] = 3000.0
    f, _ = build(tiny_v3, ASSUMPTIONS)
    a = next(x for x in f if x.branch_id == "a")            # reaches C1 (1000 adults), C2 (3000)
    assert a.catchment_shop_rent_m2 == 3000.0                # women-weighted median: C2 holds the majority
    assert a.shop_rent_coverage == pytest.approx(1.0)
    assert a.site_rent_m2 == 1000.0 and a.site_rent_source == "dld"   # a sits in C1
    b = next(x for x in f if x.branch_id == "b")            # sits in C3: no shop rent there
    assert b.site_rent_m2 is None and b.site_rent_source == "none" and b.women_per_rent_k is None


def test_shop_rent_never_changes_a_label(real_v3):
    from src.model import growth, scorecard
    f, areas = build(real_v3, ASSUMPTIONS)
    before = {d.branch_id: d.action for d in scorecard.decide(f)}
    real_v3.cells["shop_rent_m2"] = real_v3.cells.get("shop_rent_m2") * 10
    from src.features import lounges
    lounges._PREP.clear()
    f2, areas2 = build(real_v3, ASSUMPTIONS)
    real_v3.cells["shop_rent_m2"] = real_v3.cells["shop_rent_m2"] / 10
    assert {d.branch_id: d.action for d in scorecard.decide(f2)} == before
    assert [d.action for d in growth.classify_all(areas2)] == [d.action for d in growth.classify_all(areas)]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --extra dev --extra notebook pytest tests/features/test_lounges.py -k "rent" -v`
Expected: FAIL with ImportError on `women_per_rent_k`.

- [ ] **Step 3: Implement**

`src/data_v3.py:_cells`: after the affluence join, add the shop rent, tolerating a missing file:

```python
    shop = d / "cell_shop_rent.csv"
    cells["shop_rent_m2"] = (pd.read_csv(shop).set_index("cell_id").shop_rent_m2
                             if shop.exists() else pd.Series(dtype=float)).reindex(cells.index)
```

`src/models.py`: add to `LoungeFeatures` (after `premium_reviews_per_1k`):

```python
    site_rent_m2: float | None = None            # shop rent at the lounge's site, AED/m2/yr: our cost (display only)
    site_rent_source: str = "none"               # dld | band | none
    catchment_shop_rent_m2: float | None = None  # women-weighted median over catchment cells with one
    shop_rent_coverage: float = 0.0              # share of catchment women in cells with a shop rent
    women_per_rent_k: float | None = None        # addressable women per AED 1,000 of the site's annual rent
```

And to `Area` (after `premium_reviews_per_1k`):

```python
    shop_rent_m2: float | None = None            # women-weighted median shop rent over the area's cells
    shop_rent_coverage: float = 0.0
    women_per_rent_k: float | None = None        # addressable women per AED 1,000 of annual rent there
```

`src/features/lounges.py`, below `MIN_RATING_REVIEWS_WHY`:

```python
REF_UNIT_M2 = 150
REF_UNIT_WHY = ("Lounge floor areas aren't public: 150 m2 is an assumed reference unit. One size "
                "for every site, so it sets the level of women-per-rent, never the ranking.")


def women_per_rent_k(women: float, rent_m2: float | None) -> float | None:
    """Addressable women per AED 1,000 of annual rent for a REF_UNIT_M2 unit; None without a rent."""
    if rent_m2 is None or rent_m2 != rent_m2 or rent_m2 <= 0:
        return None
    return women / (rent_m2 * REF_UNIT_M2 / 1000)


def _shop_rent(cs: list[str], w: dict, shop: dict) -> tuple[float | None, float]:
    """Women-weighted median shop rent over these cells, and the share of women it covers."""
    obs = [c for c in cs if shop.get(c) == shop.get(c) and shop.get(c) is not None]
    total = sum(w[c] for c in cs)
    return (weighted_median([shop[c] for c in obs], [w[c] for c in obs]),
            sum(w[c] for c in obs) / total if total else 0.0)
```

In `build`, add `shop = v3.cells.shop_rent_m2.to_dict() if "shop_rent_m2" in v3.cells else {}` next to `rents = rent.to_dict()`. Then, inside the lounge loop, find the lounge's own cell:

```python
        site_cell = next((c for c in cs if p["cell"][c]["lat"] - 0.01 <= lo.lat < p["cell"][c]["lat"] + 0.01
                          and p["cell"][c]["lng"] - 0.01 <= lo.lng < p["cell"][c]["lng"] + 0.01), None)
        site = shop.get(site_cell) if site_cell else None
        site = None if site is None or site != site else float(site)
        c_rent, c_cov = _shop_rent(cs, w, shop)
```

and pass these to `LoungeFeatures(...)`:

```python
            site_rent_m2=site, site_rent_source="dld" if site is not None else "none",
            catchment_shop_rent_m2=c_rent, shop_rent_coverage=c_cov,
            women_per_rent_k=women_per_rent_k(addressable, site),
```

In `_area`, give it a `shop` argument (update the single call site in `build`), then compute and pass:

```python
    a_rent, a_cov = _shop_rent(piece, w, shop)
    ...
                shop_rent_m2=a_rent, shop_rent_coverage=a_cov,
                women_per_rent_k=women_per_rent_k(sum(aw[c] for c in piece), a_rent),
```

- [ ] **Step 4: Run the tests to verify they pass, then the full suite**

Run: `uv run --extra dev --extra notebook pytest tests/features -v` → PASS.
Run: `uv run --extra dev --extra notebook pytest -q` → fully green. The fact sheets don't change until Task 4.

- [ ] **Step 5: Commit**

```bash
git add src/data_v3.py src/models.py src/features/lounges.py tests/features/test_lounges.py
git commit -m "Shop rent and women per AED 1k of rent for lounges, catchments and areas (Dubai; display only)"
git push origin main
```

---

### Task 3: Published retail rent bands outside Dubai (research + data)

**Files:**
- Create: `data/seed/v3/retail_rent_bands.csv` with columns `emirate, location_class, low_m2, base_m2, high_m2, source_title, source_url, published, notes`
- Create: `data/seed/v3/lounge_site_class.csv` with columns `branch_id, location_class, evidence` (one row per scored non-Dubai lounge)
- Modify: `data/seed/v3/SOURCES.md` (new section "Commercial rent")
- Test: `tests/test_data_v3.py`

**Interfaces:**
- Produces: both CSVs. `location_class` ∈ {`super_regional_mall`, `regional_mall`, `community_mall`, `street`}. All values are AED/m²/yr (convert AED/sqft × 10.764).

- [ ] **Step 1: Research (time-box: 2 hours; stop and report if it fails)**

Find **public, dated** retail rent figures for Abu Dhabi first (15 lounges, every SHRINK), then Sharjah, Ras Al Khaimah and Fujairah. Candidates:
- Quarterly UAE real estate market reports from CBRE, JLL, Knight Frank, Cavendish Maxwell, ValuStrat and Asteco. They usually publish retail rent ranges by city and mall class in AED/sqft/yr.
- ADREC or DARI (Abu Dhabi) published reports. Their ArcGIS service refused data before (SOURCES.md, "ADREC").

Rules:
- Every row needs `source_url` and `published` (≤ 18 months old).
- If a source gives a single figure, set `low_m2 = base_m2 = high_m2` and say so in `notes`.
- Never scrape listing portals: Bayut and Property Finder are against their terms (SOURCES.md).
- **If no citable Abu Dhabi source exists, stop here.** Report it, and ship Dubai-only, with the limitation stated in Task 5.

- [ ] **Step 2: Classify each non-Dubai scored lounge**

For each lounge, use the address in `data/seed/v3/branches.csv` (e.g. "Deerfields Mall, Shop 419B" → `regional_mall`). Write `evidence` as the address fragment that justifies the class. Leave the airport out (NOT SCORED).

- [ ] **Step 3: Write the failing test**

```python
# append to tests/test_data_v3.py
def test_retail_rent_bands_are_sourced_and_ordered():
    import pandas as pd
    from src.config import REPO_ROOT
    v3 = REPO_ROOT / "data" / "seed" / "v3"
    bands = pd.read_csv(v3 / "retail_rent_bands.csv")
    assert bands.source_url.str.startswith("http").all() and bands.published.notna().all()
    assert (bands.low_m2 <= bands.base_m2).all() and (bands.base_m2 <= bands.high_m2).all()
    assert bands.base_m2.between(200, 15_000).all()                      # AED/m2/yr, not per sqft
    classes = pd.read_csv(v3 / "lounge_site_class.csv")
    assert set(classes.location_class) <= set(bands.location_class)
    assert classes.evidence.str.len().gt(0).all()
```

- [ ] **Step 4: Run the test**

Run: `uv run --extra dev --extra notebook pytest tests/test_data_v3.py -k bands -v` → FAIL until both CSVs exist, then PASS.

- [ ] **Step 5: Commit**

```bash
git add data/seed/v3/retail_rent_bands.csv data/seed/v3/lounge_site_class.csv data/seed/v3/SOURCES.md tests/test_data_v3.py
git commit -m "Published retail rent bands by emirate and mall class; non-Dubai lounge site classes (sourced)"
git push origin main
```

---

### Task 4: Use the bands for non-Dubai lounges; show it in the app and fact sheets

**Files:**
- Modify: `src/data_v3.py` (load both CSVs into `V3` as `rent_bands` and `site_class`, empty when missing)
- Modify: `src/features/lounges.py` (a site rent fallback for non-Dubai lounges)
- Modify: `src/explain.py` (`FIELDS` glossary entries; `LOUNGE_TABLE`, `AREA_TABLE`)
- Modify: `src/webapp/pages/overview.py` (Compare tables: two columns)
- Test: `tests/features/test_lounges.py`, `tests/webapp/test_pages.py`

**Interfaces:**
- Consumes: Task 2's fields; Task 3's CSVs.
- Produces: `site_rent_source == "band"` for a non-Dubai lounge with a class; `women_per_rent_k` from the band's `base_m2`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/features/test_lounges.py
def test_non_dubai_lounge_uses_its_class_band(real_v3):
    f, _ = build(real_v3, ASSUMPTIONS)
    banded = [x for x in f if x.site_rent_source == "band"]
    assert banded and all(x.emirate != "Dubai" and x.site_rent_m2 > 0 and x.women_per_rent_k for x in banded)
    assert all(x.site_rent_source in ("dld", "none") for x in f if x.emirate == "Dubai")
```

```python
# tests/webapp/test_pages.py
def test_shop_rent_shows_as_cost_with_the_unit_assumption():
    lounge = _text(_page("lounge", lounge="al-barsha"))
    assert "Shop rent at the site" in lounge and "AED/m²/yr" in lounge     # factor table label + unit
    overview = _page("overview")
    assert "Shop rent (AED/m²/yr)" in overview.dataframe[0].value.columns
    assert "Shop rent is our cost; women per AED 1k assumes a 150 m² unit." in _text(overview)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --extra dev --extra notebook pytest -k "class_band or shop_rent_shows_as_cost" -v` → FAIL.

- [ ] **Step 3: Implement**

- `src/data_v3.py`: add `rent_bands: pd.DataFrame` and `site_class: dict[str, str]` to `V3`, loaded with `pd.read_csv(...)` when the files exist, else an empty DataFrame and `{}`.
- `src/features/lounges.py`, in the lounge loop, after `site` is computed:

```python
        source = "dld" if site is not None else "none"
        cls = v3.site_class.get(b)
        if site is None and cls and lo.emirate != "Dubai":
            row = v3.rent_bands[(v3.rent_bands.emirate == lo.emirate) & (v3.rent_bands.location_class == cls)]
            if len(row):
                site, source = float(row.base_m2.iloc[0]), "band"
```

  and pass `site_rent_source=source`.
- `src/explain.py`: add `Field`s with explicit units and the reference-unit wording:

```python
    "site_rent_m2": Field("Shop rent at the site", "AED/m²/yr",
                          "Commercial (shop) rent where the lounge sits: our cost, not customer affluence. "
                          "Dubai: DLD Ejari shop contracts in its area; elsewhere: a published band for its mall class."),
    "women_per_rent_k": Field("Women per AED 1k of rent", "women",
                              "Addressable women per AED 1,000 of annual rent for a 150 m² unit (assumed): "
                              "the unit size sets the level, never the ranking. Display only, not scored."),
    "shop_rent_m2": Field("Shop rent in the area", "AED/m²/yr",
                          "Women-weighted median DLD shop rent over the area's cells (Dubai only)."),
```

  Then add `"site_rent_m2", "women_per_rent_k"` to `LOUNGE_TABLE`, and `"shop_rent_m2", "women_per_rent_k"` to `AREA_TABLE`. No other wiring is needed: `lounge_facts` and `area_facts` take every table field with `getattr` (`src/explain.py:394`, `:424`).
- `src/webapp/pages/overview.py`: in `_lounge_table` and `_area_table`, add `"Shop rent (AED/m²/yr)"` and `"Women per AED 1k rent"` columns, plus a caption line: "Shop rent is our cost; women per AED 1k assumes a 150 m² unit."

- [ ] **Step 4: Run the tests**

Run: `uv run --extra dev --extra notebook pytest -q`. Expected: green, except the 3 cache-freshness tests, because the fact sheets changed.

- [ ] **Step 5: Regenerate the explanations offline (no API)**

```bash
uv run python -m src.explain prompts data/raw/explain_v8
# write each answer to data/raw/explain_v8/answers/<file> named in its prompt (grounded; no money claims
# beyond the rent figure itself; shop rent framed as cost; never advise renegotiating rent: out of scope)
uv run python -m src.explain check data/raw/explain_v8
uv run python -m src.explain ingest data/raw/explain_v8
uv run --extra dev --extra notebook pytest -q        # fully green
```

- [ ] **Step 6: Commit**

```bash
git add src/data_v3.py src/features/lounges.py src/explain.py src/webapp/pages/overview.py \
        tests/features/test_lounges.py tests/webapp/test_pages.py data/explanations/cache.json
git commit -m "Shop rent and women-per-rent for every lounge (DLD in Dubai, published bands elsewhere); app and fact sheets"
git push origin main
```

---

### Task 5: Docs, sanity run 5, rubric

**Files:**
- Modify: `CONTEXT.md` (terms: **Shop rent**, **Women per rent**; *Avoid*: "rent" unqualified)
- Modify: `README.md` (signal/data table row; "What we simplified": the reference unit; the Q→data table)
- Modify: `docs/limitations.md`:
  - The Dubai area median mixes mall and street shops.
  - Bands are coarse class averages, not the lounge's lease.
  - The reference unit is assumed.
  - Display only, and why (rent tracks revenue too).
- Modify: `docs/data-inventory.md` (rows for both new files, with licences: DLD open data; each report's terms)
- Modify: `docs/sanity-checks.md` (run 5 results for SC7 and BT6 against Task 0; run log row)
- Modify: `docs/rubric.md`:
  - OB5: "fixed site cost" has a source.
  - DA1 and S6 notes.
  - An audit-log row.

- [ ] **Step 1: Run SC7 and BT6 and write the results under Task 0's expectations**

```bash
uv run python - <<'EOF'
import pandas as pd
from src.baseline import run
a = pd.read_csv("data/seed/v3/dubai_shop_rents_by_area.csv")
a = a[a.match != "unmatched"]
print("SC7 areas:", len(a), "median", a.median_rent_m2.median(), "outside 300-10000:",
      (~a.median_rent_m2.between(300, 10_000)).mean())
r = run(); d = {x.branch_id: x.action for x in r.decisions}
rows = sorted(((f.women_per_rent_k, f.branch_id, d[f.branch_id], f.site_rent_source) for f in r.features
               if f.women_per_rent_k), reverse=True)
for row in rows: print("BT6", row)
EOF
```

- [ ] **Step 2: Verify the docs' numbers against `run()` and AppTest renders**

Run: `uv run --extra dev --extra notebook pytest -q` (green). Then grep the docs for every new number and re-derive it.

- [ ] **Step 3: Commit**

```bash
git add CONTEXT.md README.md docs/limitations.md docs/data-inventory.md docs/sanity-checks.md docs/rubric.md
git commit -m "Commercial rent: docs, sanity run 5 (SC7, BT6), rubric OB5 site-cost source"
git push origin main
```

---

## Out of this plan (next)

- **ROIC gate (OB5):** site cost = `site_rent_m2 × unit m²` + fit-out amortisation, against a revenue assumption (visits × price × margin). This is the place where rent should affect decisions.
- **Mall-level Dubai rents:** DLD `PROJECT_EN` / `MASTER_PROJECT_EN` might isolate mall projects, which is better than the area median for mall lounges. Check before relying on it.
- **Per-area outlier trimming,** if a reviewer wants it.
