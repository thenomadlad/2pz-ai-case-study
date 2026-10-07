"""One-off: pull Dubai beauty/hair salons from OSM Overpass into data/seed/competitors.csv.

Run manually (`uv run python scripts/fetch_competitors.py`); the app and pipeline only
ever read the committed CSV. OSM coverage in Dubai is patchy -- treat counts as a lower bound.
"""
import csv
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

QUERY = """
[out:json][timeout:120];
(
  nwr["shop"="beauty"]({bbox});
  nwr["shop"="hairdresser"]({bbox});
);
out center tags;
"""
# Seed communities/branches span 24.986-25.298N, 55.115-55.445E; pad ~3 km.
# ponytail: bbox not the AE-DU admin area (area queries 504 on public Overpass), so a
# sliver of Sharjah north-east of Al Qusais leaks in; clip by polygon if that matters.
BBOX = "24.95,55.08,25.33,55.48"
OUT = Path(__file__).resolve().parents[1] / "data" / "seed" / "competitors.csv"


def is_competitor(tags: dict) -> bool:
    if "bedashing" in tags.get("name", "").lower():
        return False  # our own branches
    if tags.get("hairdresser") == "barber" or tags.get("male") == "yes":
        return False  # men-only, not Bedashing's competitive set
    # Most Dubai gents' salons are tagged plain shop=hairdresser; catch them by name.
    return not MALE_NAME.search(tags.get("name", ""))


MALE_NAME = re.compile(r"\b(gents?|men|man|barber|barbershop|barbers)\b", re.IGNORECASE)


def refilter_existing() -> None:
    """Re-apply is_competitor to the committed CSV without hitting Overpass again."""
    rows = [r for r in csv.DictReader(OUT.open()) if is_competitor({"name": r["name"]})]
    _write(rows)
    print(f"{len(rows)} competitors kept in {OUT}")


def _write(rows: list[dict]) -> None:
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "name", "category", "lat", "lng"])
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    req = urllib.request.Request(
        "https://overpass-api.de/api/interpreter",
        data=urllib.parse.urlencode({"data": QUERY.replace("{bbox}", BBOX)}).encode(),
        headers={"User-Agent": "2pz-ai-case-study/1.0"},
    )
    elements = json.load(urllib.request.urlopen(req, timeout=180))["elements"]
    rows = []
    for el in elements:
        tags = el.get("tags", {})
        if not is_competitor(tags):
            continue
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lng = el.get("lon") or el.get("center", {}).get("lon")
        if lat is None or lng is None:
            continue
        rows.append({"id": f"osm-{el['type'][0]}{el['id']}", "name": tags.get("name", ""),
                     "category": tags["shop"], "lat": round(lat, 6), "lng": round(lng, 6)})
    rows.sort(key=lambda r: r["id"])
    _write(rows)
    print(f"{len(elements)} OSM elements -> {len(rows)} competitors written to {OUT}")


if __name__ == "__main__":
    import sys
    refilter_existing() if "--refilter" in sys.argv else main()
