"""One-off: shop asking rent per ~2 km cell in the northern emirates (Sharjah, Ajman, RAK, UAQ, Fujairah).

Source: asking rents from Property Finder / Bayut shop-for-rent listings, collected 2026-10-11 via
third-party Apify scrapers (lentic_clockss~property-finder-uae-scraper, logiover~bayut-scraper).
Scraping listing portals is a ToS grey area, accepted by the owner and disclosed. Asking rents, not
signed contracts (Dubai uses DLD Ejari contracts, scripts/build_shop_rent.py): expect them above
achieved rents.

Raw (gitignored): data/raw/listings/pf_*.json, bayut_*.json. No API calls here.
PF coverage: all of RAK/UAQ/Fujairah; Sharjah and Ajman fetched in price bands (free-plan cap of
60 rows per search), ~95% of the live count. Bayut: first 201 (RAK/UAQ/Fujairah) and 250
(Sharjah+Ajman, default order) results only, budget-capped.

1. Normalise to rows; keep yearly rents with area_sqft > MIN_SQFT and AED/sqft within JUNK bounds.
2. De-duplicate across portals: same emirate, within DUP_M and price within DUP_PRICE (keep PF).
3. Exclusions agreed with the owner (2026-10-11), kept in the clean file with `excluded`:
   industrial (location path matches the growth model's NON_RESIDENTIAL pattern: an industrial
   unit is not a lounge site) and building_cap (at most BUILDING_CAP listings per building, i.e.
   per cluster of pins within BUILDING_M, so one agent's 50 units in one block can't set a cell).
4. Per cell: median AED/m2 of the K nearest listings within RADIUS_KM in the same emirate;
   n_used < MIN_N -> emirate median, fallback=True.

Outputs (data/seed/v3/): listing_rents_clean.csv, cell_listing_rent.csv
Run: uv run python scripts/build_listing_rent.py
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.model.growth import NON_RESIDENTIAL  # noqa: E402
RAW, V3 = ROOT / "data/raw/listings", ROOT / "data/seed/v3"
EMIRATES = ["Sharjah", "Ajman", "Ras Al Khaimah", "Umm Al Quwain", "Fujairah"]
SQFT_PER_M2 = 10.764
MIN_SQFT = 50
JUNK = (5, 1000)  # AED/sqft/yr; outside is a typo (monthly price, sale price, wrong area)
DUP_M, DUP_PRICE = 50, 0.05
K, RADIUS_KM, MIN_N = 10, 5, 5
BUILDING_M, BUILDING_CAP = 30, 3


def load() -> pd.DataFrame:
    rows = []
    for f in glob.glob(str(RAW / "pf_*.json")):
        for x in json.load(open(f)):
            rows.append(dict(source="propertyfinder", emirate=x["locationTree"][0]["name"],
                             listing_id=str(x["id"]), lat=x["latitude"], lng=x["longitude"],
                             area_sqft=x["size"] if x.get("sizeUnit") == "sqft" else np.nan,
                             annual_rent_aed=x["priceAmount"], period=x["pricePeriod"],
                             location_path=" > ".join(t["name"] for t in x["locationTree"])))
    for f in glob.glob(str(RAW / "bayut_*.json")):
        for x in json.load(open(f)):
            rows.append(dict(source="bayut", emirate=x["city"], listing_id=str(x["externalID"]),
                             lat=x["latitude"], lng=x["longitude"], area_sqft=x["areaSqft"],
                             annual_rent_aed=x["price"], period=x["rentFrequency"],
                             location_path=x["locationPath"]))
    return pd.DataFrame(rows).drop_duplicates(["source", "listing_id"])


def km(lat1, lng1, lat2, lng2):
    """Haversine, broadcasting."""
    p1, p2, dl = np.radians(lat1), np.radians(lat2), np.radians(lng2 - lng1)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))


def dedup(df: pd.DataFrame) -> pd.DataFrame:
    """Drop a Bayut row that matches a PF row (same emirate, < DUP_M apart, price within DUP_PRICE)."""
    pf, by = df[df.source == "propertyfinder"], df[df.source == "bayut"]
    drop = []
    for i, b in by.iterrows():
        p = pf[pf.emirate == b.emirate]
        near = km(b.lat, b.lng, p.lat.values, p.lng.values) * 1000 < DUP_M
        close = abs(p.annual_rent_aed.values / b.annual_rent_aed - 1) <= DUP_PRICE
        if (near & close).any():
            drop.append(i)
    print(f"cross-portal duplicates dropped: {len(drop)}")
    return df.drop(drop)


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw[raw.emirate.isin(EMIRATES)].copy()
    df["aed_per_sqft"] = df.annual_rent_aed / df.area_sqft
    keep = ((df.period == "yearly") & (df.area_sqft > MIN_SQFT) & df.lat.notna()
            & df.aed_per_sqft.between(*JUNK))
    print("dropped (not yearly / area <= 50 sqft / no coords / junk AED/sqft):")
    print(df[~keep].groupby(["emirate", "source"]).size().to_string())
    print("junk AED/sqft values:", sorted(df[~df.aed_per_sqft.between(*JUNK)].aed_per_sqft.round(1)))
    df = dedup(df[keep])
    df["aed_per_m2"] = df.aed_per_sqft * SQFT_PER_M2
    return df.drop(columns="period").round({"aed_per_sqft": 2, "aed_per_m2": 1})


def exclude(df: pd.DataFrame) -> pd.DataFrame:
    """`excluded`: industrial | building_cap | '' (see 3. above). Buildings: greedy clusters of pins
    within BUILDING_M of a cluster's first pin; the BUILDING_CAP kept are the lowest listing ids."""
    df = df.sort_values(["emirate", "listing_id"]).reset_index(drop=True)
    df["excluded"] = np.where(df.location_path.map(lambda x: bool(NON_RESIDENTIAL.search(x))), "industrial", "")
    ok = df[df.excluded == ""]
    building = pd.Series("", index=ok.index)
    for em, g in ok.groupby("emirate"):
        centres = []
        for i, r in g.iterrows():
            d = km(r.lat, r.lng, np.array([c[0] for c in centres]), np.array([c[1] for c in centres])) * 1000 \
                if centres else np.array([])
            j = int(d.argmin()) if len(d) and d.min() <= BUILDING_M else None
            if j is None:
                centres.append((r.lat, r.lng))
                j = len(centres) - 1
            building[i] = f"{em}:{j}"
    capped = building.groupby(building).cumcount() >= BUILDING_CAP
    df.loc[capped[capped].index, "excluded"] = "building_cap"
    print("excluded:\n" + df.groupby(["emirate", "excluded"]).size().unstack(fill_value=0).to_string())
    return df


def per_cell(listings: pd.DataFrame, cells: pd.DataFrame) -> pd.DataFrame:
    listings = listings[listings.excluded == ""]
    out = []
    for em, cs in cells[cells.emirate.isin(EMIRATES)].groupby("emirate"):
        ls = listings[listings.emirate == em]
        em_median = ls.aed_per_m2.median()
        d = km(cs.lat.values[:, None], cs.lng.values[:, None], ls.lat.values[None], ls.lng.values[None])
        for j, cid in enumerate(cs.cell_id):
            idx = np.argsort(d[j])[:K]
            idx = idx[d[j][idx] <= RADIUS_KM]
            n = len(idx)
            fb = n < MIN_N
            out.append(dict(cell_id=cid, emirate=em, n_used=n, fallback=fb,
                            listing_rent_m2=round(em_median if fb else float(np.median(ls.aed_per_m2.values[idx])), 1)))
    return pd.DataFrame(out)[["cell_id", "emirate", "listing_rent_m2", "n_used", "fallback"]]


def main() -> None:
    raw = load()
    print("raw:\n" + raw.groupby(["emirate", "source"]).size().to_string())
    listings = exclude(clean(raw))
    print("kept:\n" + listings.groupby(["emirate", "source"]).size().to_string())
    print("median AED/m2 per emirate (counted):\n"
          + listings[listings.excluded == ""].groupby("emirate").aed_per_m2.median().round(0).to_string())
    listings.to_csv(V3 / "listing_rents_clean.csv", index=False)
    cells = per_cell(listings, pd.read_csv(V3 / "cells.csv"))
    print("cells direct / fallback:\n" + cells.groupby(["emirate", "fallback"]).size().unstack(fill_value=0).to_string())
    cells.to_csv(V3 / "cell_listing_rent.csv", index=False)


if __name__ == "__main__":
    assert abs(km(25, 55, 25, 56) - 100.9) < 1  # 1 deg lng at 25N ~ 101 km
    main()
