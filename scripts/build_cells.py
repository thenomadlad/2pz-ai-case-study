"""One-off: market size per ~2 km grid cell, for every populated cell in the UAE.

Market size = women aged 15+. Built from:
- WorldPop 2025 R2025A age/sex rasters (100 m, constrained), female + male bands 15-90+, in
  data/raw/worldpop/ (see data/seed/v3/SOURCES.md for the URLs). WorldPop applies one national
  sex ratio (33.6% female) to every cell, so we keep its *adults* per cell and redo the split:
- OSM landuse=industrial (data/raw/osm/landuse_industrial.json) marks worker housing. Adults
  there are `worker_share` female (calibrated on Dubai Statistics Center community data);
  every other cell gets the residential share that keeps each emirate's WorldPop female total.

The split is not baked in: cells.csv stores adults and worker-housing adults, emirates.csv the
totals, so the notebook and the app can recompute women for any worker_share
(`worker_housing_female_share` in data/scenarios/baseline.yaml).

Cell names: OSM admin boundary (level 10, then 8) containing the centre, else the nearest OSM
place within 3 km, else the emirate.

Run: uv run --extra notebook python scripts/build_cells.py [--force]
"""
import csv
import glob
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "seed" / "v3"
CELL_PX = 24          # 24 x 3 arc-seconds = 0.02 deg: ~2.2 km N-S x ~2.0 km E-W at 24.5 N
MIN_ADULTS = 500      # cells with fewer adults are left out (desert, farms, empty plots)
PLACE_MAX_KM = 3.0
EMIRATE = {"Abu Dhabi Emirate": "Abu Dhabi", "Dubai Emirate": "Dubai", "Sharjah Emirate": "Sharjah",
           "Ajman Emirate": "Ajman", "Umm al-Quwain Emirate": "Umm Al Quwain",
           "Ras al-Khaimah Emirate": "Ras Al Khaimah", "Fujairah Emirate": "Fujairah"}


def block_sum(a: np.ndarray, k: int) -> np.ndarray:
    """Sum k x k pixel blocks; ragged edges are zero-padded."""
    h, w = -(-a.shape[0] // k) * k, -(-a.shape[1] // k) * k
    p = np.zeros((h, w), dtype=a.dtype)
    p[:a.shape[0], :a.shape[1]] = a
    return p.reshape(h // k, k, w // k, k).sum(axis=(1, 3))


def _polygons(elements: list[dict]):
    """OSM ways/relations with geometry -> shapely polygons (outer rings only)."""
    from shapely.geometry import LineString, Polygon
    from shapely.ops import polygonize, unary_union
    for e in elements:
        if e["type"] == "way" and len(e.get("geometry", [])) >= 4:
            pts = [(p["lon"], p["lat"]) for p in e["geometry"]]
            if pts[0] == pts[-1]:
                yield e, Polygon(pts)
        elif e["type"] == "relation":
            lines = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
                     for m in e.get("members", [])
                     if m["type"] == "way" and m.get("role") in ("outer", "") and m.get("geometry")]
            if lines:
                g = unary_union(list(polygonize(unary_union(lines))))
                if not g.is_empty:
                    yield e, g


def _read_adults(sex: str):
    import rasterio
    total, transform = None, None
    files = sorted(glob.glob(str(RAW / "worldpop" / f"are_{sex}_*_2025_CN_100m_R2025A_v1.tif")))
    if len(files) != 16:
        raise SystemExit(f"expected 16 {sex} rasters (ages 15-90+) in data/raw/worldpop, found {len(files)}")
    for f in files:
        with rasterio.open(f) as r:
            a = r.read(1, masked=True).filled(0).astype("float32")
            total = a if total is None else total + a
            transform = r.transform
    return total, transform


def main() -> None:
    if (OUT / "cells.csv").exists() and "--force" not in sys.argv:
        raise SystemExit(f"{OUT / 'cells.csv'} exists; pass --force to rebuild")
    from rasterio import features
    from shapely import STRtree
    from shapely.geometry import Point

    women, transform = _read_adults("f")
    men, _ = _read_adults("m")
    adults = women + men

    admin = json.loads((RAW / "osm" / "admin_boundaries.json").read_text())["elements"]
    polys = [(e["tags"], g) for e, g in _polygons(admin)]
    emirates = {EMIRATE[t.get("name:en") or t["name"]]: g for t, g in polys
                if t.get("admin_level") == "4" and (t.get("name:en") or t.get("name")) in EMIRATE}
    em_names = sorted(emirates)
    em_px = features.rasterize([(g, i + 1) for i, (n, g) in enumerate((n, emirates[n]) for n in em_names)],
                               out_shape=adults.shape, transform=transform, dtype="uint8")

    industrial = [g for _, g in _polygons(json.loads((RAW / "osm" / "landuse_industrial.json").read_text())["elements"])]
    ind_px = features.rasterize([(g, 1) for g in industrial], out_shape=adults.shape,
                                transform=transform, dtype="uint8").astype(bool)
    worker = np.where(ind_px, adults, 0)

    with open(OUT / "emirates.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["emirate", "adults", "women_worldpop", "worker_adults"])
        for i, n in enumerate(em_names, start=1):
            m = em_px == i
            w.writerow([n, round(float(adults[m].sum())), round(float(women[m].sum())), round(float(worker[m].sum()))])

    A, W, F = (block_sum(x, CELL_PX) for x in (adults, worker, women))
    E = block_sum((em_px > 0).astype("float32"), CELL_PX)   # pixels on land in each cell
    rows, cols = np.nonzero((A >= MIN_ADULTS) & (E > 0))

    named = [(t.get("admin_level"), t.get("name:en") or t.get("name"), g) for t, g in polys
             if t.get("admin_level") in ("8", "10") and (t.get("name:en") or t.get("name"))]
    places = [p for p in json.loads((RAW / "osm" / "places.json").read_text())["elements"]
              if p["tags"].get("name:en") or p["tags"].get("name")]
    place_tree = STRtree([Point(p["lon"], p["lat"]) for p in places])
    em_tree, em_list = STRtree([emirates[n] for n in em_names]), em_names
    from src.features.lounges import haversine_km

    out = []
    step = CELL_PX * transform.a
    for r, c in zip(rows, cols):
        west, north = transform * (c * CELL_PX, r * CELL_PX)
        south, east = north - step, west + step
        lat, lng = north - step / 2, west + step / 2
        pt = Point(lng, lat)
        hit = em_tree.query(pt, predicate="intersects")
        if len(hit):
            emirate = em_list[hit[0]]
        else:   # cell centre in the sea or just over a border: nearest emirate
            emirate = em_list[int(em_tree.nearest(pt))]
        name, source = None, None
        for level in ("10", "8"):
            name = next((n for lvl, n, g in named if lvl == level and g.contains(pt)), None)
            if name:
                source = f"osm_admin_{level}"
                break
        if not name:
            p = places[int(place_tree.nearest(pt))]
            if haversine_km(lat, lng, p["lat"], p["lon"]) <= PLACE_MAX_KM:
                name, source = p["tags"].get("name:en") or p["tags"]["name"], "osm_place"
            else:
                name, source = emirate, "emirate"
        out.append({"cell_id": f"r{r}c{c}", "lat": round(lat, 5), "lng": round(lng, 5),
                    "south": round(south, 5), "west": round(west, 5), "north": round(north, 5),
                    "east": round(east, 5), "emirate": emirate, "name": name, "name_source": source,
                    "adults": round(float(A[r, c])), "adults_worker": round(float(W[r, c])),
                    "women_worldpop": round(float(F[r, c]))})

    with open(OUT / "cells.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"wrote {len(out)} cells ({sum(o['adults'] for o in out) / adults[em_px > 0].sum():.1%} "
          f"of UAE adults) and {len(em_names)} emirates")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    main()
