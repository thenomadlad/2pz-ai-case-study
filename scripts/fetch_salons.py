"""One-off: candidate competitors for each Bedashing lounge, from Google Places.

The 15-min catchments are covered with small circles (CIRCLE_M radius, hexagonal grid, no gaps);
each circle gets one Nearby Search for women's-salon primary types, ranked by POPULARITY (20
results). Locally, popularity ranking finds the most-reviewed salons: on a fully swept tile
around Al Barsha it recovered 17 of the true top 20 premium salons by reviews, where one large
text search found 0-2 and one large popularity search 5 (validation in notebooks/competitors.ipynb).
Results from the earlier per-lounge text searches (cached) are merged in at no cost. A lounge's
candidates are the salons inside its 15-min polygon; other Bedashing lounges inside it are added
from branches.csv, so lounges with overlapping catchments compete (cannibalisation).

Nothing is selected here: the notebook and the app pick each lounge's premium substitutes from
lounge_candidates.csv with the baseline.yaml values (competitor_coverage, premium_min_rating,
comparable_price_levels, search_recall), so changing them costs nothing.

Each call asks for rating, review count and price ("Enterprise": 1,000 free calls a month).
One call per circle (576 for the 15-min catchments at 1,800 m); MAX_CALLS stops it before the free tier
runs out. Responses are cached per circle in data/raw/places_cache/, so a crash or a re-run costs
nothing.

Outputs (data/seed/v3/): salons.csv (one row per salon, with excluded_reason),
lounge_candidates.csv (branch_id, place_id: non-excluded candidates, the lounge itself left out),
and lounge_search_saturation.csv (per lounge: circles over its catchment and how many came back
full; feeds recall_multiplier).

Second mode, `growth` (2026-10-09, paid ~$7, approved): the same circles over populated cells
outside every lounge's 15-min catchment (>= GROWTH_MIN_WOMEN women 15+), so growth areas can be
judged on competition too. Writes growth_salons.csv and adds those circles to search_circles.csv.
search_circles.csv records every circle (both modes): centre, radius, results, and whether it hit
Google's cap, so the recall correction can be computed for any grouping of cells.

Run: uv run --extra notebook python scripts/fetch_salons.py [--force]
     uv run --extra notebook python scripts/fetch_salons.py growth
"""
import csv
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import scripts.places as places  # noqa: E402
from scripts.places import is_bedashing, search, to_row  # noqa: E402,F401
from src.market import (SALON_TYPES, capture, capture_by_coverage, coverage_k,  # noqa: E402,F401
                        excluded_reason, premium_substitutes, recall_multiplier)

V3 = ROOT / "data" / "seed" / "v3"
CACHE = ROOT / "data" / "raw" / "places_cache"
QUERIES = ("beauty salon", "ladies salon")   # the earlier text searches, merged in from cache
CIRCLE_M = 1800        # 576 circles for the 15-min catchments: inside the free tier (1,500 m needed 770)
FULL = 20              # Nearby Search returns at most 20: a full circle may hold more
MAX_CALLS = 620        # the run is cached: a re-run costs 0. Never raise this without approval
GROWTH_MIN_WOMEN = 2000
GROWTH_MAX_CALLS = 300  # approved 2026-10-09: 282 circles, ~$7 beyond the free tier


def dedupe(rows: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in rows:
        if r["place_id"] not in seen:
            seen.add(r["place_id"])
            out.append(r)
    return out


def fetch_lounge(branch: dict, polygon, cache_dir: Path) -> list[dict]:
    """Raw Places results for every query inside the polygon's bounding box; cached per query."""
    w, s, e, n = polygon.bounds
    found = []
    for q in QUERIES:
        key = hashlib.sha1(json.dumps([q, [round(x, 5) for x in (s, w, n, e)]]).encode()).hexdigest()
        path = Path(cache_dir) / f"lounge_{key}.json"
        if path.exists():
            found += json.loads(path.read_text())
            continue
        res_all, token = [], None
        for _ in range(3):
            body = {"textQuery": q, "pageSize": 20, "locationRestriction": {"rectangle": {
                "low": {"latitude": s, "longitude": w}, "high": {"latitude": n, "longitude": e}}}}
            if token:
                body["pageToken"] = token
            res = search(body, paged=True)
            res_all += res.get("places", [])
            token = res.get("nextPageToken")
            if not token:
                break
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(res_all))
        found += res_all
    return found


def circles(area, radius_m: float = CIRCLE_M) -> list[tuple[float, float]]:
    """(lat, lng) centres of a gap-free hexagonal cover of the area by radius_m circles."""
    from math import cos, radians, sqrt
    from shapely.affinity import scale
    from shapely.geometry import Point
    w, s, e, n = area.bounds
    r_lat = radius_m / 111_000
    out, row, lat = [], 0, s
    while lat <= n + r_lat:
        r_lng = r_lat / cos(radians(lat))
        lng = w + (sqrt(3) * r_lng / 2 if row % 2 else 0)
        while lng <= e + r_lng:
            if area.intersects(scale(Point(lng, lat).buffer(r_lat), xfact=1 / cos(radians(lat)))):
                out.append((round(lat, 6), round(lng, 6)))
            lng += sqrt(3) * r_lng
        lat += 1.5 * r_lat
        row += 1
    return out


def fetch_circle(lat: float, lng: float, radius_m: float, cache_dir: Path) -> list[dict]:
    """Top 20 women's salons by Google popularity within the circle; cached per circle."""
    key = hashlib.sha1(json.dumps(["nearby", round(lat, 5), round(lng, 5), radius_m]).encode()).hexdigest()
    path = Path(cache_dir) / f"nearby_{key}.json"
    if path.exists():
        return json.loads(path.read_text())
    body = {"includedPrimaryTypes": sorted(SALON_TYPES), "maxResultCount": 20,
            "rankPreference": "POPULARITY", "locationRestriction": {"circle": {
                "center": {"latitude": lat, "longitude": lng}, "radius": radius_m}}}
    res = search(body, url=places.NEARBY_URL).get("places", [])
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(res))
    return res


def growth_cells(women, catchment, level: str, min_women: float) -> list[str]:
    """Cells with at least min_women women 15+ that no lounge's catchment reaches at `level`."""
    inside = set(catchment.loc[catchment.level == level, "cell_id"])
    return [c for c, w in women.items() if w >= min_women and c not in inside]


def _write_circles(rows: list[dict]) -> None:
    """Upsert circles into search_circles.csv (keyed by purpose, lat, lng, radius)."""
    path = V3 / "search_circles.csv"
    old = list(csv.DictReader(open(path))) if path.exists() else []
    key = lambda r: (r["purpose"], str(r["lat"]), str(r["lng"]), str(r["radius_m"]))
    merged = {key(r): r for r in old} | {key(r): r for r in rows}
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["purpose", "lat", "lng", "radius_m", "results", "full"])
        w.writeheader()
        w.writerows(merged.values())


def tag_bedashing(rows: list[dict], branches: list[dict]) -> list[dict]:
    by_place = {b["place_id"]: b["branch_id"] for b in branches if b.get("place_id")}
    return [r | {"is_bedashing": r["place_id"] in by_place
                 or is_bedashing({"displayName": {"text": r.get("name") or ""}}),
                 "branch_id": by_place.get(r["place_id"], "")} for r in rows]


def _read(name):
    with open(V3 / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    if (V3 / "salons.csv").exists() and "--force" not in sys.argv:
        raise SystemExit(f"{V3 / 'salons.csv'} exists; pass --force to rebuild")
    import yaml
    from shapely import make_valid
    from shapely.geometry import Point, shape
    from scripts.fetch_isochrones import polygons, ranges_minutes

    from shapely.ops import unary_union

    places.MAX_CALLS = MAX_CALLS
    a = yaml.safe_load(open(ROOT / "data" / "scenarios" / "baseline.yaml"))["assumptions"]
    levels, depart_at = a["travel_time_minutes"], a["isochrone_depart_at"]
    branches = _read("branches.csv")
    polys = {b["branch_id"]: make_valid(shape(polygons(float(b["lat"]), float(b["lng"]),
                                                       ranges_minutes(levels), depart_at)[levels["medium"]]))
             for b in branches}                                         # from the isochrone cache
    cs = circles(unary_union(list(polys.values())))
    print(f"{len(cs)} circles of {CIRCLE_M} m cover the {levels['medium']}-min catchments")
    found = []
    for i, (lat, lng) in enumerate(cs, start=1):
        found += fetch_circle(lat, lng, CIRCLE_M, CACHE)
        if i % 100 == 0:
            print(f"  {i}/{len(cs)} circles, {places.calls} billed calls")
    for b in branches:                                                 # cached text searches
        found += fetch_lounge(b, polys[b["branch_id"]], CACHE)
    pool = dedupe([to_row(p) for p in found])
    pool += [{"place_id": o["place_id"], "name": o["name"], "address": o["address"],
              "lat": float(o["lat"]), "lng": float(o["lng"]), "rating": o["rating"],
              "review_count": o["review_count"], "status": o["status"], "primary_type": "beauty_salon",
              "price_level": "", "price_low_aed": None, "price_high_aed": None}
             for o in branches if o["place_id"]]
    pool = tag_bedashing(dedupe(pool), branches)
    today = date.today().isoformat()
    salons, pairs = {}, []
    for b in branches:
        poly = polys[b["branch_id"]]
        rows = [r for r in pool if poly.contains(Point(r["lng"], r["lat"]))]
        for r in rows:
            r["excluded_reason"] = excluded_reason(r)
            salons.setdefault(r["place_id"], r | {"fetched_at": today})
            if not r["excluded_reason"] and r["place_id"] != b["place_id"]:
                pairs.append({"branch_id": b["branch_id"], "place_id": r["place_id"]})
        n = sum(1 for p in pairs if p["branch_id"] == b["branch_id"])
        print(f"{b['branch_id']:30} {len(rows):4} salons in catchment, {n:4} candidates")

    # How saturated each catchment's search was: share of the circles over it that came back full.
    from math import cos, radians
    from shapely.affinity import scale
    full = {(la, ln): len(fetch_circle(la, ln, CIRCLE_M, CACHE)) >= FULL for la, ln in cs}   # cached
    disks = {k: scale(Point(k[1], k[0]).buffer(CIRCLE_M / 111_000), xfact=1 / cos(radians(k[0]))) for k in full}
    saturation = []
    for b in branches:
        over = [k for k, d in disks.items() if d.intersects(polys[b["branch_id"]])]
        saturation.append({"branch_id": b["branch_id"], "circles": len(over),
                           "full_circles": sum(full[k] for k in over),
                           "full_share": round(sum(full[k] for k in over) / len(over), 4) if over else 0.0})

    rows = list(salons.values())
    with open(V3 / "salons.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    _write_circles([{"purpose": "catchment", "lat": la, "lng": ln, "radius_m": CIRCLE_M,
                     "results": len(fetch_circle(la, ln, CIRCLE_M, CACHE)), "full": full[(la, ln)]}
                    for la, ln in cs])
    with open(V3 / "lounge_search_saturation.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(saturation[0]))
        w.writeheader()
        w.writerows(saturation)
    with open(V3 / "lounge_candidates.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["branch_id", "place_id"])
        w.writeheader()
        w.writerows(pairs)
    print(f"wrote {len(rows)} salons ({sum(1 for r in rows if not r['excluded_reason'])} candidates), "
          f"{len(pairs)} lounge-candidate pairs; {places.calls} billed calls")


def growth() -> None:
    """Competitors around populated cells outside every catchment (see the module docstring)."""
    import yaml
    from shapely.geometry import box
    from shapely.ops import unary_union
    from src.market import women_15plus

    places.MAX_CALLS = GROWTH_MAX_CALLS
    a = yaml.safe_load(open(ROOT / "data" / "scenarios" / "baseline.yaml"))["assumptions"]
    cells = {r["cell_id"]: r for r in _read("cells.csv")}
    import pandas as pd
    cdf = pd.read_csv(V3 / "cells.csv").set_index("cell_id")
    women = women_15plus(cdf, pd.read_csv(V3 / "emirates.csv").set_index("emirate"),
                         a["worker_housing_female_share"]["medium"])
    ids = growth_cells(women, pd.read_csv(V3 / "catchment_cells.csv"), "medium", GROWTH_MIN_WOMEN)
    area = unary_union([box(float(cells[c]["west"]), float(cells[c]["south"]),
                            float(cells[c]["east"]), float(cells[c]["north"])) for c in ids])
    cs = circles(area)
    print(f"{len(ids)} growth cells (>= {GROWTH_MIN_WOMEN:,} women, outside every "
          f"{a['travel_time_minutes']['medium']}-min catchment): {len(cs)} circles")
    if len(cs) > GROWTH_MAX_CALLS:
        raise SystemExit(f"{len(cs)} circles > GROWTH_MAX_CALLS={GROWTH_MAX_CALLS}; not approved")
    found, circle_rows = [], []
    for i, (lat, lng) in enumerate(cs, start=1):
        res = fetch_circle(lat, lng, CIRCLE_M, CACHE)
        found += res
        circle_rows.append({"purpose": "growth", "lat": lat, "lng": lng, "radius_m": CIRCLE_M,
                            "results": len(res), "full": len(res) >= FULL})
        if i % 50 == 0:
            print(f"  {i}/{len(cs)} circles, {places.calls} billed calls")
    today = date.today().isoformat()
    rows = tag_bedashing(dedupe([to_row(p) for p in found]), _read("branches.csv"))
    rows = [r | {"excluded_reason": excluded_reason(r), "fetched_at": today} for r in rows]
    with open(V3 / "growth_salons.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    _write_circles(circle_rows)
    print(f"wrote {len(rows)} salons ({sum(1 for r in rows if not r['excluded_reason'])} candidates) "
          f"from {len(cs)} circles ({sum(r['full'] for r in circle_rows)} full); {places.calls} billed calls")


if __name__ == "__main__":
    growth() if sys.argv[1:2] == ["growth"] else main()
