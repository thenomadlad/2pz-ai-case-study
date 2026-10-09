"""Shared Google Places (New) Text Search client for the one-off fetch scripts.

Every call asks for `rating`, so it bills at the Enterprise tier (1,000 free per month).
MAX_CALLS is a per-process hard stop; scripts lower it to what they expect to use.
Google's terms allow storing place_id indefinitely; refresh the rest within 30 days.
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import settings  # noqa: E402
from src.features.assign import haversine_km as km  # noqa: E402,F401

URL = "https://places.googleapis.com/v1/places:searchText"
FIELDS = ("places.id,places.displayName,places.formattedAddress,places.location,"
          "places.rating,places.userRatingCount,places.businessStatus,places.primaryType")
MAX_CALLS = 150
calls = 0


def search(body: dict, *, paged: bool = False) -> dict:
    global calls
    if not settings.google_maps_api_key:
        raise SystemExit("GOOGLE_MAPS_API_KEY missing from .env")
    if calls >= MAX_CALLS:
        raise SystemExit(f"stopped at MAX_CALLS={MAX_CALLS}")
    calls += 1
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.google_maps_api_key,
        "X-Goog-FieldMask": FIELDS + (",nextPageToken" if paged else ""),
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Places API {e.code} after {calls} calls: {e.read().decode()}")


def circle(lat: float, lng: float, radius_m: float) -> dict:
    return {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": radius_m}}


def name_of(place: dict) -> str:
    return place.get("displayName", {}).get("text", "")


def is_bedashing(place: dict) -> bool:
    return "bedashing" in name_of(place).lower()


def _km_to(place: dict, lat: float, lng: float) -> float:
    loc = place["location"]
    return km(lat, lng, loc["latitude"], loc["longitude"])


def best_match(places: list[dict], lat: float, lng: float, title: str = "",
               max_km: float = 1.0) -> dict | None:
    """The Bedashing listing for a lounge: one naming `title` (in its name or address),
    else the nearest within max_km of (lat, lng); None rather than a guess. Name first,
    because the store locator's own pins are off by up to 16 km in Abu Dhabi."""
    ours = [p for p in places if is_bedashing(p)]
    t = title.lower()
    named = [p for p in ours if t and (t in name_of(p).lower()
                                       or t in p.get("formattedAddress", "").lower())]
    near = [p for p in ours if _km_to(p, lat, lng) <= max_km]
    return min(named or near, key=lambda p: _km_to(p, lat, lng), default=None)


def to_row(place: dict) -> dict:
    loc = place.get("location", {})
    return {
        "place_id": place["id"], "name": name_of(place),
        "address": place.get("formattedAddress", ""),
        "lat": loc.get("latitude"), "lng": loc.get("longitude"),
        "rating": place.get("rating"), "review_count": place.get("userRatingCount"),
        "status": place.get("businessStatus"), "primary_type": place.get("primaryType"),
    }
