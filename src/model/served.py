"""Served vs unserved demand (Huff). Each cell's addressable women split across the premium suppliers
that reach it within 20 min (our lounges + premium salons), weight = reviews ** ALPHA x DECAY[band],
plus an OUTSIDE option (women who go elsewhere / no premium salon): what it takes is unserved.

Reach: the cell's own Mapbox isochrones (10/15/20 min) where fetched (810 cells inside some lounge's
20-min reach); elsewhere straight-line km bands fitted on those cells (KM_PER_BAND, fitted at load).
Quick first cut, 2026-10-11: parameters are starting points to examine, not calibrated."""
import json
import statistics

import numpy as np
import pandas as pd
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from src.config import REPO_ROOT
from src.market import _reviews, premium_substitutes

ALPHA = 1.0
DECAY = {10: 1.0, 15: 0.5, 20: 0.25}
BANDS = (10, 15, 20)
OUTSIDE_PCTL = 50
RATING_ELASTICITY = 5.0   # attractiveness x (rating / 4.6) ** 5: 4.8 stars ~1.24x, 4.3 ~0.71x; missing rating = 1x   # outside option = the median premium supplier's attractiveness, at 10 min
_ACCESS: dict[int, tuple] = {}
KM_NO_FIT = {10: 5.0, 15: 8.0, 20: 12.0}   # straight-line bands for a V3 without isochrones (tests only)


def _suppliers(v3, a, closed=frozenset(), not_scored=frozenset()) -> pd.DataFrame:
    s = v3.salons[(v3.salons.excluded_reason == "") & ~v3.salons.is_bedashing.astype(bool)]
    rows = s.reset_index().to_dict("records")
    prem = premium_substitutes(rows, len(rows), a.premium_min_rating, a.comparable_price_levels)
    sup = pd.DataFrame([{"id": r["place_id"], "lat": float(r["lat"]), "lng": float(r["lng"]),
                         "reviews": _reviews(r), "rating": r.get("rating"), "lounge": False} for r in prem],
                       columns=["id", "lat", "lng", "reviews", "rating", "lounge"])
    sup = pd.concat([sup, _imputed(v3, prem)], ignore_index=True).astype({"lat": float, "lng": float, "reviews": float})
    lo = pd.DataFrame([{"id": x.branch_id, "lat": x.lat, "lng": x.lng, "reviews": x.review_count or 0,
                        "rating": x.rating, "lounge": True}
                       for x in v3.lounges if x.branch_id not in closed and x.branch_id not in not_scored],
                      columns=["id", "lat", "lng", "reviews", "rating", "lounge"])
    return pd.concat([sup, lo], ignore_index=True).astype({"lounge": bool, "lat": float, "lng": float, "reviews": float})


IMPUTE_WHY = ("Cells our salon search never covered (remote or thinly searched) have no known competitors, so a "
              "new lounge there would look like it takes everything. Each such cell gets one stand-in "
              "competitor whose reviews = the premium reviews per 1k women of SEARCHED cells in the "
              "same emirate and density tier (tertile of women per cell; total reviews / total women, since most single cells hold none), x the cell's women. Assumption, "
              "2026-10-11: supply is like that of comparable searched places in the same emirate.")
_IMPUTED: dict[int, tuple] = {}


def _imputed(v3, prem: list[dict]) -> pd.DataFrame:
    """Stand-in competitors for unsearched cells (IMPUTE_WHY). Cached per V3."""
    hit = _IMPUTED.get(id(v3))
    if hit and hit[0] is v3:
        return hit[1]
    from src.features.lounges import _prep
    from src.market import women_15plus
    c = v3.cells.copy()
    c["women"] = women_15plus(c, v3.emirates, 0.055)
    c["covered"] = c.index.map(_prep(v3)["covered"]).fillna(False).astype(bool)
    c["tier"] = c.groupby("emirate").women.transform(   # tertiles; a toy emirate under 3 cells is one tier
        lambda s: pd.qcut(s.rank(method="first"), 3, labels=False) if len(s) >= 3 else 0)
    sal = pd.DataFrame([{"lat": float(r["lat"]), "lng": float(r["lng"]), "reviews": _reviews(r)} for r in prem],
                       columns=["lat", "lng", "reviews"])
    rev = {}
    for cid, x in c.iterrows():   # premium reviews per cell, by bounds
        m = (sal.lat >= x.south) & (sal.lat < x.north) & (sal.lng >= x.west) & (sal.lng < x.east)
        rev[cid] = float(sal.reviews[m].sum())
    c["prem_reviews"] = pd.Series(rev)
    searched = c[c.covered & (c.women > 0)]
    g = searched.groupby(["emirate", "tier"])
    rate = g.prem_reviews.sum() / (g.women.sum() / 1000)   # aggregate: most single cells hold no premium salon
    out = []
    for cid, x in c[~c.covered & (c.women > 0)].iterrows():
        r = rate.get((x.emirate, x.tier), (searched.groupby('emirate').prem_reviews.sum() / (searched.groupby('emirate').women.sum() / 1000)).get(x.emirate, 0.0))
        if r * x.women / 1000 >= 1:
            out.append({"id": f"IMP:{cid}", "lat": float(x.lat), "lng": float(x.lng), "reviews": r * x.women / 1000,
                        "rating": None, "lounge": False})
    df = pd.DataFrame(out, columns=["id", "lat", "lng", "reviews", "rating", "lounge"])
    _IMPUTED[id(v3)] = (v3, df)
    return df


def _access(v3, a, not_scored) -> pd.DataFrame:
    """(cell_id, id, minutes) for every cell x supplier within 20 min. Cached per V3."""
    hit = _ACCESS.get(id(v3))
    if hit and hit[0] is v3:
        return hit[1]
    sup = _suppliers(v3, a, frozenset(), not_scored)
    tree = STRtree([Point(x, y) for x, y in zip(sup.lng, sup.lat)])
    iso = {}
    for f in json.loads((REPO_ROOT / "data/seed/v3/cell_isochrones.geojson").read_text())["features"]:
        if f["properties"]["cell_id"] in v3.cells.index:   # the real file; a test V3 has its own cells
            iso.setdefault(f["properties"]["cell_id"], {})[f["properties"]["minutes"]] = shape(f["geometry"])
    cells = v3.cells
    rows, fit = [], {b: [] for b in BANDS}
    for cid, poly in iso.items():
        seen = set()
        c = cells.loc[cid]
        for b in BANDS:
            for i in tree.query(poly[b], predicate="contains"):
                if i not in seen:
                    seen.add(i)
                    rows.append((cid, sup.id.iloc[i], b, "isochrone"))
                    fit[b].append(_km(c.lat, c.lng, sup.lat.iloc[i], sup.lng.iloc[i]))
    # straight-line band edges: the 75th pct km of pairs reached within each band (cumulative)
    # no isochrone pairs only happens on a toy V3 (tests): fall back to KM_NO_FIT
    km = {b: float(np.percentile(sum((fit[x] for x in BANDS if x <= b), []), 75)) if fit[10] else KM_NO_FIT[b]
          for b in BANDS}
    for cid, c in cells[~cells.index.isin(iso)].iterrows():
        d = _km(c.lat, c.lng, sup.lat.values, sup.lng.values)
        for i in np.flatnonzero(d <= km[20]):
            rows.append((cid, sup.id.iloc[i], next(b for b in BANDS if d[i] <= km[b]), "straight_line"))
    out = pd.DataFrame(rows, columns=["cell_id", "id", "minutes", "source"])
    _ACCESS[id(v3)] = (v3, out, km)
    return out


def _km(lat, lng, lats, lngs):
    p1, p2 = np.radians(lat), np.radians(lats)
    h = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(np.asarray(lngs) - lng) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(h))


def allocate(demand: pd.Series, acc: pd.DataFrame, sup: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Per cell: demand, served_lounges, served_competitors, unserved; per lounge: women served."""
    a = acc.merge(sup[["id", "reviews", "rating", "lounge"]], on="id")
    stars = pd.to_numeric(a.rating, errors="coerce").fillna(4.6)
    a["w"] = a.reviews.clip(lower=1) ** ALPHA * (stars / 4.6) ** RATING_ELASTICITY * a.minutes.map(DECAY)
    outside = float(np.percentile(sup.reviews.clip(lower=1) ** ALPHA, OUTSIDE_PCTL)) if len(sup) else 1.0   # no supplier left (toy V3)
    denom = a.groupby("cell_id").w.sum() + outside
    a["women"] = a.w / a.cell_id.map(denom) * a.cell_id.map(demand).fillna(0.0)
    cells = pd.DataFrame({"demand": demand})
    cells["served_lounges"] = a[a.lounge].groupby("cell_id").women.sum()
    cells["served_competitors"] = a[~a.lounge].groupby("cell_id").women.sum()
    cells = cells.fillna(0.0)
    cells["unserved"] = cells.demand - cells.served_lounges - cells.served_competitors
    return cells, a[a.lounge].groupby("id").women.sum()


def served(v3, a, demand: pd.Series, closed=frozenset(), not_scored=frozenset()) -> dict:
    """Served women per open lounge, unserved per cell, and per lounge the share of its served women
    its siblings absorb if it closes (leave-one-out)."""
    acc = _access(v3, a, not_scored)
    sup = _suppliers(v3, a, closed, not_scored)
    acc = acc[acc.id.isin(sup.id)]
    cells, by_lounge = allocate(demand, acc, sup)
    lounges = sup[sup.lounge].id.tolist()
    absorbed = {}
    for b in lounges:
        mine = by_lounge.get(b, 0.0)
        if not mine:
            absorbed[b] = None
            continue
        _, after = allocate(demand, acc[acc.id != b], sup[sup.id != b])
        gain = sum(after.get(x, 0.0) - by_lounge.get(x, 0.0) for x in lounges if x != b)
        absorbed[b] = gain / mine
    return {"cells": cells, "served": by_lounge.to_dict(), "absorbed": absorbed}


def site_access(v3, a, lat: float, lng: float, not_scored=frozenset()) -> pd.DataFrame:
    """(cell_id, minutes) for every cell that reaches a point within 20 min: its own isochrone where
    fetched, else the fitted straight-line bands."""
    _access(v3, a, not_scored)
    km = _ACCESS[id(v3)][2]
    iso = _ISO.get(id(v3))
    if iso is None:
        iso = {}
        for f in json.loads((REPO_ROOT / "data/seed/v3/cell_isochrones.geojson").read_text())["features"]:
            if f["properties"]["cell_id"] in v3.cells.index:
                iso.setdefault(f["properties"]["cell_id"], {})[f["properties"]["minutes"]] = shape(f["geometry"])
        _ISO[id(v3)] = iso
    pt, rows, cells = Point(lng, lat), [], v3.cells
    for cid, poly in iso.items():
        b = next((b for b in BANDS if poly[b].contains(pt)), None)
        if b:
            rows.append((cid, b))
    other = cells[~cells.index.isin(iso)]
    d = _km(lat, lng, other.lat.values, other.lng.values)
    for i in np.flatnonzero(d <= km[20]):
        rows.append((other.index[i], next(b for b in BANDS if d[i] <= km[b])))
    return pd.DataFrame(rows, columns=["cell_id", "minutes"])


_ISO: dict[int, dict] = {}


def what_if_open(v3, a, demand: pd.Series, lat: float, lng: float, reviews: float, rating: float | None,
                 closed=frozenset(), not_scored=frozenset()) -> dict:
    """Open a typical lounge at (lat, lng): the women it would serve, and how many of them it takes
    from our existing lounges (the rest is new to the network)."""
    acc = _access(v3, a, not_scored)
    sup = _suppliers(v3, a, closed, not_scored)
    acc = acc[acc.id.isin(sup.id)]
    _, before = allocate(demand, acc, sup)
    new = site_access(v3, a, lat, lng, not_scored).assign(id="NEW", source="what_if")
    sup2 = pd.concat([sup, pd.DataFrame([{"id": "NEW", "lat": lat, "lng": lng, "reviews": reviews,
                                          "rating": rating, "lounge": True}])], ignore_index=True)
    _, after = allocate(demand, pd.concat([acc, new], ignore_index=True), sup2)
    served = float(after.get("NEW", 0.0))
    taken = float(before.sum() - after.drop("NEW", errors="ignore").sum())
    return {"served": served, "taken_from_lounges": taken, "net_new": served - taken}
