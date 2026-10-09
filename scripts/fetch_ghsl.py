"""One-off: built form per ~2 km cell, from the EU JRC Global Human Settlement Layer (free, 2018).

An affluence proxy for every cell in the UAE, to be calibrated on Dubai rents
(scripts/build_affluence.py). In a desert city, irrigated greenery and low-rise detached housing
(villas) cost money; towers are mixed (Marina expensive, International City cheap), so the
calibration decides what each feature is worth.

- GHS-BUILT-C MSZ R2023A (10 m, Mollweide): per pixel, open space (1-3 vegetation low/medium/high,
  4 water, 5 road) or built space, residential (11-15) / non-residential (21-25) by height band
  (<=3, 3-6, 6-15, 15-30, >30 m).
- GHS-BUILT-H ANBH R2023A (100 m): average net building height.

Tiles R6-R7 x C23-C24 cover the UAE (GHSL 54009 tile schema). Downloads are cached in
data/raw/ghsl/ (~160 MB, free, no key). Output: data/seed/v3/cell_built_form.csv with, per cell:
res_share (residential / built), villa_share (residential <= 6 m / residential), tower_share
(residential > 15 m / residential), green_share (medium+high vegetation / settlement), mean_height.

Run: uv run --extra notebook python scripts/fetch_ghsl.py
"""
import csv
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "ghsl"
OUT = ROOT / "data" / "seed" / "v3" / "cell_built_form.csv"
BASE = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL"
TILES = ("R6_C23", "R6_C24", "R7_C23", "R7_C24")
PRODUCTS = {
    "msz": f"{BASE}/GHS_BUILT_C_GLOBE_R2023A/GHS_BUILT_C_MSZ_E2018_GLOBE_R2023A_54009_10/V1-0/tiles/"
           "GHS_BUILT_C_MSZ_E2018_GLOBE_R2023A_54009_10_V1_0_{t}.zip",
    "height": f"{BASE}/GHS_BUILT_H_GLOBE_R2023A/GHS_BUILT_H_ANBH_E2018_GLOBE_R2023A_54009_100/V1-0/tiles/"
              "GHS_BUILT_H_ANBH_E2018_GLOBE_R2023A_54009_100_V1_0_{t}.zip",
}


def tif(product: str, tile: str) -> Path:
    """The tile's GeoTIFF, downloaded and unzipped once."""
    zpath = RAW / Path(PRODUCTS[product].format(t=tile)).name
    if not zpath.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        print(f"downloading {zpath.name}")
        urllib.request.urlretrieve(PRODUCTS[product].format(t=tile), zpath)
    with zipfile.ZipFile(zpath) as z:
        name = next(n for n in z.namelist() if n.endswith(".tif"))
        if not (RAW / name).exists():
            z.extract(name, RAW)
    return RAW / name


def shares(px: np.ndarray) -> dict:
    """Built-form shares from MSZ class counts (0 / NoData pixels ignored)."""
    c = np.bincount(px.ravel(), minlength=26)
    res, built = c[11:16].sum(), c[11:16].sum() + c[21:26].sum()
    settlement = built + c[1:6].sum()
    def div(a, b):
        return round(float(a / b), 4) if b else None

    return {"res_share": div(res, built), "villa_share": div(c[11] + c[12], res),
            "tower_share": div(c[14] + c[15], res), "green_share": div(c[2] + c[3], settlement)}


def main() -> None:
    import rasterio
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds

    with open(ROOT / "data" / "seed" / "v3" / "cells.csv") as f:
        cells = list(csv.DictReader(f))
    acc = {c["cell_id"]: {"msz": [], "height": []} for c in cells}
    for product in PRODUCTS:
        for tile in TILES:
            with rasterio.open(tif(product, tile)) as src:
                for c in cells:
                    b = transform_bounds("EPSG:4326", src.crs, float(c["west"]), float(c["south"]),
                                         float(c["east"]), float(c["north"]))
                    if b[2] <= src.bounds.left or b[0] >= src.bounds.right or \
                       b[3] <= src.bounds.bottom or b[1] >= src.bounds.top:
                        continue
                    w = from_bounds(*b, transform=src.transform).round_offsets().round_lengths()
                    a = src.read(1, window=w, boundless=True, fill_value=0)
                    acc[c["cell_id"]][product].append(a.ravel())
            print(f"{product} {tile} done")
    rows = []
    for cid, d in acc.items():
        msz = np.concatenate(d["msz"]) if d["msz"] else np.zeros(0, dtype="uint8")
        h = np.concatenate(d["height"]).astype(float) if d["height"] else np.zeros(0)
        h = h[(h > 0) & (h < 1000)]
        rows.append({"cell_id": cid, **shares(msz.astype("int64").clip(0, 25)),
                     "mean_height": round(float(h.mean()), 2) if h.size else None})
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} cells to {OUT}")


if __name__ == "__main__":
    main()
