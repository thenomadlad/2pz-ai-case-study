"""One-off: drive-time isochrones from the Mapbox Isochrone API, in two stages.

  lounges  For each lounge, polygons at every catchment level and at 2x each level (the
           competitor bound): 10, 15, 20, 30, 40 min with the default assumptions. Writes
           lounge_isochrones.geojson and catchment_cells.csv (cells whose centre is inside a
           lounge's catchment, per level). 2 requests per lounge (max 4 contours each).
  cells    For every cell inside some lounge's catchment (at the high level), polygons at each
           catchment level, starting from the cell's centre (customers drive from home).
           Writes cell_isochrones.geojson. One request per cell.

Profile `driving-traffic` with `depart_at` = `isochrone_depart_at` in baseline.yaml: Mapbox's
typical traffic at that time. Every response is cached in data/raw/isochrone_cache/mapbox/, so a
re-run or a crash costs nothing. (openrouteservice was tried first: its free key allows ~250
isochrones a day, counted per location, so 808 cells would take days.)

Run: uv run --extra notebook python scripts/fetch_isochrones.py lounges|cells
(needs MAPBOX_ACCESS_TOKEN in .env; free tier ~100k isochrone requests a month, 300 a minute)
"""
import csv
import hashlib
import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml
from shapely.geometry import Point, mapping, shape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.config import settings  # noqa: E402

V3 = ROOT / "data" / "seed" / "v3"
CACHE = ROOT / "data" / "raw" / "isochrone_cache" / "mapbox"
URL = "https://api.mapbox.com/isochrone/v1/mapbox/driving-traffic/{lng},{lat}"
MAX_CONTOURS = 4     # Mapbox: at most 4 contours per request
OFFLINE = False     # set by offline callers (fetch_salons.py pool): a cache miss raises, no request
PAUSE_S = 0.25       # Mapbox: 300 requests a minute


def reaches(isochrone, points: dict[str, tuple[float, float]]) -> list[str]:
    """Ids of the (lat, lng) points inside the polygon."""
    return [k for k, (lat, lng) in points.items() if isochrone.contains(Point(lng, lat))]


def ranges_minutes(levels: dict[str, int]) -> list[int]:
    """Catchment levels plus 2x each (the competitor bound), deduplicated."""
    return sorted({m for v in levels.values() for m in (v, 2 * v)})


def batches(items: list, n: int) -> list[list]:
    return [items[i:i + n] for i in range(0, len(items), n)]


def _ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def isochrone(lat: float, lng: float, minutes: list[int], depart_at: str) -> list[dict]:
    """Mapbox polygons for one location, one feature per contour; cached by request."""
    params = {"contours_minutes": ",".join(map(str, minutes)), "polygons": "true",
              "denoise": "1", "depart_at": depart_at}
    key = hashlib.sha1(json.dumps([round(lat, 5), round(lng, 5), params], sort_keys=True).encode()).hexdigest()
    path = CACHE / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())["features"]
    if OFFLINE:
        raise RuntimeError(f"offline: isochrone cache miss for {lat},{lng} {params}")
    if not settings.mapbox_access_token:
        raise SystemExit("MAPBOX_ACCESS_TOKEN missing from .env")
    url = URL.format(lat=lat, lng=lng) + "?" + urllib.parse.urlencode(
        params | {"access_token": settings.mapbox_access_token})
    try:
        with urllib.request.urlopen(url, timeout=60, context=_ssl_context()) as r:
            out = json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Mapbox {e.code}: {e.read().decode()[:500]}")
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out))
    time.sleep(PAUSE_S)
    return out["features"]


def polygons(lat: float, lng: float, minutes: list[int], depart_at: str) -> dict[int, dict]:
    """minutes -> GeoJSON geometry, splitting into requests of at most 4 contours."""
    out = {}
    for chunk in batches(minutes, MAX_CONTOURS):
        for f in isochrone(lat, lng, chunk, depart_at):
            out[int(f["properties"]["contour"])] = f["geometry"]
    return out


def _assumptions() -> tuple[dict[str, int], str]:
    a = yaml.safe_load(open(ROOT / "data" / "scenarios" / "baseline.yaml"))["assumptions"]
    return a["travel_time_minutes"], a["isochrone_depart_at"]


def _read(name: str) -> list[dict]:
    with open(V3 / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


SIMPLIFY_DEG = 0.002   # ~200 m, written files only: far below a 2 km cell, keeps the repo small.
# Memberships (which cells a lounge reaches) are computed on the full-detail polygons first.


def _write_geojson(name: str, features: list[dict]) -> None:
    out = [f | {"geometry": json.loads(json.dumps(mapping(shape(f["geometry"]).simplify(
                SIMPLIFY_DEG, preserve_topology=True))), parse_float=lambda x: round(float(x), 5))}
           for f in features]
    (V3 / name).write_text(json.dumps({"type": "FeatureCollection", "features": out},
                                      separators=(",", ":")))


def stage_lounges() -> None:
    (levels, depart_at), branches = _assumptions(), _read("branches.csv")
    features = []
    for b in branches:
        for m, geom in polygons(float(b["lat"]), float(b["lng"]), ranges_minutes(levels), depart_at).items():
            features.append({"type": "Feature", "geometry": geom,
                             "properties": {"branch_id": b["branch_id"], "minutes": m}})
    _write_geojson("lounge_isochrones.geojson", features)

    cells = {c["cell_id"]: (float(c["lat"]), float(c["lng"])) for c in _read("cells.csv")}
    rows = []
    for level, m in levels.items():
        for f in features:
            if f["properties"]["minutes"] == m:
                rows += [{"cell_id": c, "level": level, "branch_id": f["properties"]["branch_id"]}
                         for c in reaches(shape(f["geometry"]), cells)]
    with open(V3 / "catchment_cells.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["cell_id", "level", "branch_id"])
        w.writeheader()
        w.writerows(rows)
    high = {r["cell_id"] for r in rows if r["level"] == max(levels, key=levels.get)}
    print(f"{len(features)} lounge polygons; catchment cells by level: "
          + ", ".join(f"{lvl} {len({r['cell_id'] for r in rows if r['level'] == lvl})}" for lvl in levels)
          + f"; stage 'cells' needs {len(high)} requests")


def stage_cells() -> None:
    levels, depart_at = _assumptions()
    high = max(levels, key=levels.get)
    ids = sorted({r["cell_id"] for r in _read("catchment_cells.csv") if r["level"] == high})
    cells = {c["cell_id"]: (float(c["lat"]), float(c["lng"])) for c in _read("cells.csv")}
    by_minutes = {m: lvl for lvl, m in levels.items()}
    features = []
    for i, c in enumerate(ids, start=1):
        for m, geom in polygons(*cells[c], sorted(levels.values()), depart_at).items():
            features.append({"type": "Feature", "geometry": geom,
                             "properties": {"cell_id": c, "level": by_minutes[m], "minutes": m}})
        if i % 100 == 0:
            print(f"  {i}/{len(ids)} cells")
    _write_geojson("cell_isochrones.geojson", features)
    print(f"{len(features)} cell polygons for {len(ids)} cells")


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else ""
    {"lounges": stage_lounges, "cells": stage_cells}.get(
        stage, lambda: sys.exit("usage: fetch_isochrones.py lounges|cells"))()
