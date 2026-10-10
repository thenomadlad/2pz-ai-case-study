"""One-off: an affluence index per ~2 km cell from Dubai rents, extended to the UAE by built form.

1. Rents: DLD Ejari residential contracts for one unit (flats, villas, studios; labour camps,
   staff housing and bulk leases of many units left out: they aren't a household's rent), downloaded by hand from dubailand.gov.ae Open Data
   "Rents" (captcha-gated; the site serves at most 3 months: registered 2026-07-10 to 2026-10-09)
   into data/raw/dld/. Median annual rent per DLD area.
2. Areas -> points: each DLD area is matched by normalised name to an OSM admin-10 polygon centroid
   or an OSM place point inside Dubai, else the centre of the cells.csv cells carrying that name
   (spelling table + "drop the number" fallback), else ALIASES (DLD-only names, by hand).
3. Cells: a Dubai cell's observed rent is the contract-weighted median of the area medians whose
   point lies inside the cell; with none inside, the nearest area point within RADIUS_KM. Areas
   with fewer than MIN_CONTRACTS contracts are left out.
4. Built form (data/seed/v3/cell_built_form.csv, scripts/fetch_ghsl.py) -> log rent, a plain
   linear fit on the observed cells, cross-validated by name group; R2 reported. Predicted for
   every cell with residential built form if the CV R2 >= MIN_R2, else not used.

Outputs (data/seed/v3/): dubai_rents_by_area.csv, cell_affluence.csv
(cell_id, rent_observed, rent_predicted, affluence_rent, source: observed | predicted | none).
Analysis and plots: notebooks/affluence.ipynb.

Run: uv run --extra notebook python scripts/build_affluence.py
"""
import glob
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.build_cells import _polygons
from src.features.lounges import haversine_km

V3 = ROOT / "data" / "seed" / "v3"
RAW = ROOT / "data" / "raw"
HOUSEHOLD = {"Flat", "Villa", "Studio"}
RADIUS_KM = 2.5
MIN_CONTRACTS = 20
MIN_R2 = 0.3
FEATURES = ["res_share", "villa_share", "tower_share", "green_share", "mean_height"]
DUBAI = (24.6, 25.45, 54.85, 55.65)  # lat/lng box for name matching

ORDINALS = {"first": "1", "second": "2", "third": "3", "fourth": "4", "fifth": "5",
            "sixth": "6", "seventh": "7", "eighth": "8"}
SPELLING = {"jumeirah": "jumeira", "barshaa": "barsha", "nadd": "nad", "muhaisanah": "muhaisnah",
            "goze": "quoz", "jabal": "jebel", "um": "umm", "shiba": "sheba", "saffa": "safa",
            "yelayiss": "yalayis", "safouh": "sufouh", "mararr": "murar", "murqabat": "muraqqabat",
            "mamzer": "mamzar", "rega": "rigga", "suq": "souk", "thanayah": "thanyah",
            "eyal": "ayal", "nasser": "nasir", "jafliya": "jafiliya", "aweer": "awir",
            "lusaily": "lesaily", "khabeesi": "khabisi", "zaabeel": "zabeel", "center": "centre",
            "cornich": "corniche", "muragab": "muraqqabat", "suqaim": "suqeim", "bada": "badaa",
            "merkadh": "merkad"}
# DLD land-registry names with no OSM namesake: the community they are, located by hand.
ALIASES = {
    "Al Khairan First": (25.2005, 55.3520, "Dubai Creek Harbour"),
    "Marsa Dubai": (25.0805, 55.1403, "Dubai Marina"),
    "Burj Khalifa": (25.1960, 55.2780, "Downtown Dubai"),
    "Palm Jumeirah": (25.1124, 55.1390, "Palm Jumeirah"),
    "Madinat Dubai Almelaheyah": (25.2640, 55.2770, "Mina Rashid"),
    "Island 2": (25.0440, 55.1600, "Jumeirah Islands"),
    "Hatta": (24.8000, 56.1280, "Hatta"),
}


def norm(name: str) -> str:
    words = [w for w in re.split(r"[^a-z0-9]+", name.lower().replace("'", "")) if w]
    words = [ORDINALS.get(w, SPELLING.get(w, w)) for w in words]
    return " ".join(w for w in words if w not in ("al", "mbr"))


def area_rents(rents: pd.DataFrame) -> pd.DataFrame:
    """Median annual rent and AED/m² per DLD area, household contracts only."""
    r = rents[(rents.USAGE_EN == "Residential") & rents.PROP_SUB_TYPE_EN.str.strip().isin(HOUSEHOLD)
              & (rents.TOTAL_PROPERTIES == 1) & (rents.ANNUAL_AMOUNT > 0)]
    per_sqm = (r.ANNUAL_AMOUNT / r.ACTUAL_AREA).where(r.ACTUAL_AREA > 10)
    return (r.assign(per_sqm=per_sqm).groupby("AREA_EN")
            .agg(contracts=("ANNUAL_AMOUNT", "size"), median_rent=("ANNUAL_AMOUNT", "median"),
                 median_rent_per_sqm=("per_sqm", "median"),
                 villa_contract_share=("PROP_SUB_TYPE_EN", lambda s: (s.str.strip() == "Villa").mean()))
            .reset_index().rename(columns={"AREA_EN": "area"}))


def osm_points() -> dict[str, tuple[float, float, str, str]]:
    """Normalised name -> (lat, lng, OSM name, source) inside Dubai; admin-10 wins over places."""
    lo_lat, hi_lat, lo_lng, hi_lng = DUBAI
    pts = {}
    for p in json.loads((RAW / "osm" / "places.json").read_text())["elements"]:
        n = p["tags"].get("name:en") or p["tags"].get("name")
        if n and lo_lat < p["lat"] < hi_lat and lo_lng < p["lon"] < hi_lng:
            pts.setdefault(norm(n), (p["lat"], p["lon"], n, "osm_place"))
    cells = pd.read_csv(V3 / "cells.csv")
    for n, c in cells[cells.emirate == "Dubai"].groupby("name")[["lat", "lng"]].mean().iterrows():
        pts.setdefault(norm(n), (c.lat, c.lng, n, "cells_named"))
    for tags, g in _polygons(json.loads((RAW / "osm" / "admin_boundaries.json").read_text())["elements"]):
        n = tags.get("name:en") or tags.get("name")
        if tags.get("admin_level") == "10" and n:
            pts[norm(n)] = (g.centroid.y, g.centroid.x, n, "osm_admin10")
    return pts


def locate(areas: pd.DataFrame) -> pd.DataFrame:
    pts = osm_points()

    def find(area):
        if area in ALIASES:
            lat, lng, n = ALIASES[area]
            return lat, lng, n, "alias"
        key = norm(area)
        if key in pts:
            return pts[key]
        base = re.sub(r"( \d+)+$", "", key)            # "warqa 3" -> "warqa"
        if base in pts:
            lat, lng, n, _ = pts[base]
            return lat, lng, n, "osm_base_name"
        return None, None, None, "unmatched"

    found = pd.DataFrame([find(a) for a in areas.area], columns=["lat", "lng", "matched_to", "match"])
    return pd.concat([areas.reset_index(drop=True), found], axis=1)


def observed(cells: pd.DataFrame, areas: pd.DataFrame) -> pd.Series:
    """Per Dubai cell: contract-weighted median of the areas whose point is inside it, else the
    nearest area point within RADIUS_KM."""
    a = areas.dropna(subset=["lat"])
    a = a[a.contracts >= MIN_CONTRACTS]
    out = {}
    for cid, c in cells[cells.emirate == "Dubai"].iterrows():
        inside = a[(a.lat >= c.south) & (a.lat < c.north) & (a.lng >= c.west) & (a.lng < c.east)]
        if len(inside):
            inside = inside.sort_values("median_rent")
            cum = inside.contracts.cumsum()
            out[cid] = float(inside.median_rent[cum >= cum.iloc[-1] / 2].iloc[0])
            continue
        d = haversine_km(c.lat, c.lng, a.lat.values, a.lng.values)
        if d.min() <= RADIUS_KM:
            out[cid] = float(a.median_rent.iloc[d.argmin()])
    return pd.Series(out, name="rent_observed")


def fit(X: pd.DataFrame, y: pd.Series, groups: pd.Series, folds: int = 5) -> tuple[np.ndarray, float]:
    """Least squares of log rent on built form; R2 cross-validated over name groups."""
    A = np.column_stack([np.ones(len(X)), X.values])
    ly = np.log(y.values)
    g = groups.astype("category").cat.codes.values % folds
    pred = np.empty(len(ly))
    for k in range(folds):
        tr = g != k
        beta, *_ = np.linalg.lstsq(A[tr], ly[tr], rcond=None)
        pred[~tr] = A[~tr] @ beta
    r2 = 1 - ((ly - pred) ** 2).sum() / ((ly - ly.mean()) ** 2).sum()
    beta, *_ = np.linalg.lstsq(A, ly, rcond=None)
    return beta, float(r2)


def main() -> None:
    rents = pd.concat(pd.read_csv(f, encoding="utf-8-sig", low_memory=False)
                      for f in sorted(glob.glob(str(RAW / "dld" / "rents-*.csv"))))
    areas = locate(area_rents(rents))
    areas.to_csv(V3 / "dubai_rents_by_area.csv", index=False)
    matched = areas.match != "unmatched"
    print(f"{matched.sum()}/{len(areas)} DLD areas located, "
          f"{areas.contracts[matched].sum() / areas.contracts.sum():.1%} of contracts")

    cells = pd.read_csv(V3 / "cells.csv").set_index("cell_id")
    form = pd.read_csv(V3 / "cell_built_form.csv").set_index("cell_id")
    obs = observed(cells, areas)
    train = form.loc[obs.index, FEATURES].dropna()
    beta, r2 = fit(train, obs[train.index], cells.loc[train.index, "name"])
    print(f"observed rent for {len(obs)} Dubai cells; built-form fit on {len(train)}: CV R2 = {r2:.2f}")

    ok = form[FEATURES].notna().all(axis=1)
    pred = pd.Series(np.nan, index=form.index)
    pred[ok] = np.exp(np.column_stack([np.ones(ok.sum()), form.loc[ok, FEATURES].values]) @ beta)
    out = pd.DataFrame({"rent_observed": obs.reindex(form.index), "rent_predicted": pred.round(0)})
    use_pred = r2 >= MIN_R2
    out["affluence_rent"] = out.rent_observed.fillna(out.rent_predicted if use_pred else np.nan)
    out["source"] = np.where(out.rent_observed.notna(), "observed",
                             np.where(use_pred & out.rent_predicted.notna(), "predicted", "none"))
    out.index.name = "cell_id"
    out.to_csv(V3 / "cell_affluence.csv")
    print(out.source.value_counts().to_dict(), "| proxy used" if use_pred else f"| proxy NOT used (R2 < {MIN_R2})")


if __name__ == "__main__":
    main()
