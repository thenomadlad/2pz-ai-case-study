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


def _suppliers(v3, a, closed=frozenset(), not_scored=frozenset()) -> pd.DataFrame:
    s = v3.salons[(v3.salons.excluded_reason == "") & ~v3.salons.is_bedashing.astype(bool)]
    rows = s.reset_index().to_dict("records")
    prem = premium_substitutes(rows, len(rows), a.premium_min_rating, a.comparable_price_levels)
    sup = pd.DataFrame([{"id": r["place_id"], "lat": float(r["lat"]), "lng": float(r["lng"]),
                         "reviews": _reviews(r), "rating": r.get("rating"), "lounge": False} for r in prem])
    lo = pd.DataFrame([{"id": x.branch_id, "lat": x.lat, "lng": x.lng, "reviews": x.review_count or 0,
                        "rating": x.rating, "lounge": True}
                       for x in v3.lounges if x.branch_id not in closed and x.branch_id not in not_scored])
    return pd.concat([sup, lo], ignore_index=True)


def _access(v3, a, not_scored) -> pd.DataFrame:
    """(cell_id, id, minutes) for every cell x supplier within 20 min. Cached per V3."""
    hit = _ACCESS.get(id(v3))
    if hit and hit[0] is v3:
        return hit[1]
    sup = _suppliers(v3, a, frozenset(), not_scored)
    tree = STRtree([Point(x, y) for x, y in zip(sup.lng, sup.lat)])
    iso = {}
    for f in json.loads((REPO_ROOT / "data/seed/v3/cell_isochrones.geojson").read_text())["features"]:
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
    km = {b: float(np.percentile(sum((fit[x] for x in BANDS if x <= b), []), 75)) for b in BANDS}
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
    outside = float(np.percentile(sup.reviews.clip(lower=1) ** ALPHA, OUTSIDE_PCTL))
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
