"""One-off: all of Bedashing's UAE lounges, enriched with their Google Places listing.

Reads data/seed/lounges.json, a snapshot of the store locator on bedashingbeauty.com/lounges/
(`wp-admin/admin-ajax.php?action=asl_load_stores&load_all=1`; Cloudflare blocks plain HTTP,
so refresh it from a browser). Its pins are unreliable (off by up to 16 km in Abu Dhabi),
so lat/lng come from Google and the locator pin is kept as locator_lat/lng. One Text Search
per lounge; a lounge with no Bedashing listing naming it (or within 1 km of its pin) keeps
an empty place_id instead of a guessed match.

Run: uv run python scripts/fetch_branches.py [--force]   (~24 billed calls)
"""
import csv
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scripts.places as places  # noqa: E402

SEED = Path(__file__).resolve().parents[1] / "data" / "seed"
OUT = SEED / "v3" / "branches.csv"
places.MAX_CALLS = 30


def lounges() -> list[dict]:
    return [{
        # Title, not the locator's slug: slugs are stale (Noya Plaza's is
        # "zayed-international-airport-abu-dhabi").
        "branch_id": re.sub(r"[^a-z0-9]+", "-", html.unescape(lg["title"]).lower()
                            .removesuffix(" branch")).strip("-"),
        "title": html.unescape(lg["title"]),
        "emirate": (lg["state"] or lg["city"]).rstrip("."),  # City Walk has no state
        "locator_address": html.unescape(lg["street"]),
        "locator_lat": float(lg["lat"]), "locator_lng": float(lg["lng"]),
    } for lg in json.loads((SEED / "lounges.json").read_text())]


def main() -> None:
    if OUT.exists() and "--force" not in sys.argv:
        raise SystemExit(f"{OUT} exists; pass --force to re-fetch (bills again)")
    rows = []
    for lg in lounges():
        lat, lng = lg["locator_lat"], lg["locator_lng"]
        found = places.search({"textQuery": f"Bedashing Beauty Lounge {lg['title']}",
                               "locationBias": places.circle(lat, lng, 2000)})
        best = places.best_match(found.get("places", []), lat, lng, lg["title"])
        row = lg | (places.to_row(best) if best else {"place_id": None})
        if best:
            row["pin_offset_km"] = round(places.km(lat, lng, row["lat"], row["lng"]), 3)
        rows.append(row | {"fetched_at": date.today().isoformat()})
        print(f"{lg['branch_id']:40} {row.get('name') or 'NO MATCH'}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} lounges to {OUT}; {places.calls} billed calls")


if __name__ == "__main__":
    main()
