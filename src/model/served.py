"""Served vs unserved demand (Huff). Each cell's addressable women split across the premium suppliers
that reach it within 20 min (our lounges + premium salons), weight = reviews ** ALPHA x DECAY[band],
plus an OUTSIDE option (women who go elsewhere / no premium salon): what it takes is unserved.

Reach: the cell's own Mapbox isochrones (10/15/20 min) where fetched (810 cells inside some lounge's
20-min reach); elsewhere straight-line km bands fitted on those cells (KM_PER_BAND, fitted at load).
Quick first cut, 2026-10-11: parameters are starting points to examine, not calibrated.

Two assumption levels reach the split (LEVELS_WHY): drive time sets the decay across the bands
(decay(minutes)) and competitor coverage scales the competitors' pull (competitor_scale)."""
import hashlib
import json

import numpy as np
import pandas as pd
import shapely
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from src.config import REPO_ROOT
from src.market import _reviews, premium_substitutes

ALPHA = 1.0
DECAY = {10: 1.0, 15: 0.5, 20: 0.25}
BANDS = (10, 15, 20)
BASE_MINUTES = 15        # travel_time_minutes at medium: DECAY as written
BASE_COVERAGE = 0.6      # competitor_coverage at medium: competitors at full pull
LEVELS_WHY = (
    "Drive time: DECAY halves a supplier's pull every 5 min past 10, which is the medium level (15 min: "
    "the 15-min band at half the 10-min pull). At T minutes the exponent is stretched by 5 / (T - 10): "
    "10 min (low) keeps only the 10-min band, 20 min (high) flattens it (15 min 0.71x, 20 min 0.5x). "
    "Reach can't go past 20 min (no longer isochrones), so the levels move the decay, not the edge. "
    "Competitor coverage: the old capture counted the most-reviewed premium salons holding this share of "
    "the catchment's premium reviews, so competitor pull was proportional to it. Here every competitor's "
    "(and stand-in's) pull is scaled by coverage / 0.6: 0.83x at low, 1x at medium, 1.17x at high. "
    "Medium reproduces the baseline exactly; the frozen salon-site reference stays at baseline.")


def decay(minutes: float = BASE_MINUTES) -> dict[int, float]:
    """Band weights at this drive time (LEVELS_WHY); DECAY itself at BASE_MINUTES."""
    if minutes <= BANDS[0]:
        return {b: DECAY[b] if b == BANDS[0] else 0.0 for b in BANDS}
    return {b: DECAY[b] ** ((BASE_MINUTES - BANDS[0]) / (minutes - BANDS[0])) for b in BANDS}


def competitor_scale(coverage: float = BASE_COVERAGE) -> float:
    return coverage / BASE_COVERAGE
OUTSIDE_PCTL = 50
RATING_ELASTICITY = 5.0   # attractiveness x (rating / 4.6) ** 5: 4.8 stars ~1.24x, 4.3 ~0.71x; missing rating = 1x   # outside option = the median premium supplier's attractiveness, at 10 min
_ACCESS: dict[int, tuple] = {}
_ISO: dict[int, tuple] = {}
ISO_FILE = REPO_ROOT / "data/seed/v3/cell_isochrones.geojson"
ACCESS_CACHE = REPO_ROOT / ".cache"   # gitignored; a stale file is never read (its name is the inputs' hash)
KM_NO_FIT = {10: 5.0, 15: 8.0, 20: 12.0}   # straight-line bands for a V3 without isochrones (tests only)


_COMPETITORS: dict[tuple, tuple] = {}


def _competitors(v3, a) -> pd.DataFrame:
    """Premium salons plus imputed stand-ins. Cached per V3, premium rule and _imputed (a notebook swaps it)."""
    key = (id(v3), _imputed, a.premium_min_rating, tuple(a.comparable_price_levels))
    hit = _COMPETITORS.get(key)
    if hit and hit[0] is v3:
        return hit[1]
    s = v3.salons[(v3.salons.excluded_reason == "") & ~v3.salons.is_bedashing.astype(bool)]
    rows = s.reset_index().to_dict("records")
    prem = premium_substitutes(rows, len(rows), a.premium_min_rating, a.comparable_price_levels)
    sup = pd.DataFrame([{"id": r["place_id"], "lat": float(r["lat"]), "lng": float(r["lng"]),
                         "reviews": _reviews(r), "rating": r.get("rating"), "lounge": False} for r in prem],
                       columns=["id", "lat", "lng", "reviews", "rating", "lounge"])
    sup = pd.concat([sup, _imputed(v3, prem)], ignore_index=True).astype({"lat": float, "lng": float, "reviews": float})
    _COMPETITORS[key] = (v3, sup)
    return sup


def _suppliers(v3, a, closed=frozenset(), not_scored=frozenset()) -> pd.DataFrame:
    sup = _competitors(v3, a)
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
    slat, slng = sal.lat.to_numpy()[:, None], sal.lng.to_numpy()[:, None]   # premium reviews per cell, by bounds
    m = ((slat >= c.south.to_numpy()) & (slat < c.north.to_numpy())
         & (slng >= c.west.to_numpy()) & (slng < c.east.to_numpy()))       # salons x cells
    c["prem_reviews"] = sal.reviews.to_numpy(float) @ m
    searched = c[c.covered & (c.women > 0)]
    g = searched.groupby(["emirate", "tier"])
    rate = g.prem_reviews.sum() / (g.women.sum() / 1000)   # aggregate: most single cells hold no premium salon
    ge = searched.groupby("emirate")
    rate_e = ge.prem_reviews.sum() / (ge.women.sum() / 1000)   # a tier with no searched cells: the emirate's
    out = []
    for cid, x in c[~c.covered & (c.women > 0)].iterrows():
        r = rate.get((x.emirate, x.tier), rate_e.get(x.emirate, 0.0))
        if r * x.women / 1000 >= 1:
            out.append({"id": f"IMP:{cid}", "lat": float(x.lat), "lng": float(x.lng), "reviews": r * x.women / 1000,
                        "rating": None, "lounge": False})
    df = pd.DataFrame(out, columns=["id", "lat", "lng", "reviews", "rating", "lounge"])
    _IMPUTED[id(v3)] = (v3, df)
    return df


def _iso(v3) -> dict:
    """{cell_id: {minutes: polygon}} for the cells with fetched isochrones. Cached per V3."""
    hit = _ISO.get(id(v3))
    if hit and hit[0] is v3:
        return hit[1]
    iso = {}
    for f in json.loads(ISO_FILE.read_text())["features"]:
        if f["properties"]["cell_id"] in v3.cells.index:   # the real file; a test V3 has its own cells
            iso.setdefault(f["properties"]["cell_id"], {})[f["properties"]["minutes"]] = shape(f["geometry"])
    _ISO[id(v3)] = (v3, iso)
    return iso


def _access(v3, a, not_scored) -> pd.DataFrame:
    """(cell_id, id, minutes) for every cell x supplier within 20 min. Cached per V3 in memory, and on
    disk (ACCESS_CACHE) keyed on the suppliers, the cells and the isochrone file."""
    hit = _ACCESS.get(id(v3))
    if hit and hit[0] is v3:
        return hit[1]
    sup = _suppliers(v3, a, frozenset(), not_scored)
    cells = v3.cells
    h = hashlib.sha256()
    for part in (pd.util.hash_pandas_object(sup[["id", "lat", "lng"]], index=False),
                 pd.util.hash_pandas_object(cells[["lat", "lng"]], index=True)):
        h.update(part.to_numpy().tobytes())
    h.update(ISO_FILE.read_bytes() if ISO_FILE.exists() else b"")
    path = ACCESS_CACHE / f"access-{h.hexdigest()[:16]}.pkl"
    if path.exists():
        out, km = pd.read_pickle(path)
        _ACCESS[id(v3)] = (v3, out, km)
        return out
    sid, slat, slng = sup.id.to_numpy(), sup.lat.to_numpy(float), sup.lng.to_numpy(float)
    tree = STRtree([Point(x, y) for x, y in zip(slng, slat)])
    iso = _iso(v3)
    clat, clng = cells.lat.to_dict(), cells.lng.to_dict()
    rows, fit = [], {b: [] for b in BANDS}
    for cid, poly in iso.items():
        seen = set()
        for b in BANDS:
            new = [i for i in tree.query(poly[b], predicate="contains") if i not in seen]
            seen.update(new)
            rows += [(cid, sid[i], b, "isochrone") for i in new]
            fit[b] += list(_km(clat[cid], clng[cid], slat[new], slng[new]))
    # straight-line band edges: the 75th pct km of pairs reached within each band (cumulative)
    # no isochrone pairs only happens on a toy V3 (tests): fall back to KM_NO_FIT
    km = {b: float(np.percentile([k for x in BANDS if x <= b for k in fit[x]], 75)) if fit[10] else KM_NO_FIT[b]
          for b in BANDS}
    rest = cells[~cells.index.isin(iso)]
    for cid, lat, lng in zip(rest.index, rest.lat.to_numpy(float), rest.lng.to_numpy(float)):
        d = _km(lat, lng, slat, slng)
        for i in np.flatnonzero(d <= km[20]):
            rows.append((cid, sid[i], next(b for b in BANDS if d[i] <= km[b]), "straight_line"))
    out = pd.DataFrame(rows, columns=["cell_id", "id", "minutes", "source"])
    _ACCESS[id(v3)] = (v3, out, km)
    if fit[10]:   # real isochrones only: a toy V3 (tests) leaves no files behind
        ACCESS_CACHE.mkdir(parents=True, exist_ok=True)
        pd.to_pickle((out, km), path)
    return out


def _km(lat, lng, lats, lngs):
    p1, p2 = np.radians(lat), np.radians(lats)
    h = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(np.asarray(lngs) - lng) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(h))


def _arrays(acc: pd.DataFrame, sup: pd.DataFrame, minutes: float = BASE_MINUTES, cscale: float = 1.0) -> dict:
    """allocate's inputs as numpy: per access row its weight, cell code and supplier row (inner join on id).
    `minutes` and `cscale` are the drive time and competitor scale (LEVELS_WHY)."""
    j = pd.Index(sup.id).get_indexer(acc.id)
    keep = j >= 0
    j = j[keep]
    stars = pd.to_numeric(sup.rating, errors="coerce").fillna(4.6).to_numpy(float)
    ws = sup.reviews.clip(lower=1).to_numpy(float) ** ALPHA * (stars / 4.6) ** RATING_ELASTICITY
    codes, cell_ids = pd.factorize(acc.cell_id.to_numpy()[keep])
    lounge = sup.lounge.to_numpy(bool)[j]
    band = acc.minutes.to_numpy()[keep]
    return {"w": _weights(ws[j], band, lounge, minutes, cscale), "code": codes, "cells": pd.Index(cell_ids),
            "minutes": minutes, "ws": ws[j], "band": band, "sup": j, "lounge": lounge, "ids": sup.id.to_numpy(), "reviews": sup.reviews.to_numpy(float)}


def _weights(ws: np.ndarray, band: np.ndarray, lounge: np.ndarray, minutes: float, cscale: float) -> np.ndarray:
    """Per access row: supplier attractiveness x band decay at this drive time x competitor scale."""
    return ws * pd.Series(band).map(decay(minutes)).to_numpy(float) * np.where(lounge, 1.0, cscale)


def _outside(reviews: np.ndarray) -> float:
    return float(np.percentile(np.clip(reviews, 1, None) ** ALPHA, OUTSIDE_PCTL)) if len(reviews) else 1.0   # no supplier left (toy V3)


def _alloc(x: dict, demand: pd.Series, w: np.ndarray, outside: float) -> tuple[np.ndarray, np.ndarray]:
    """Women per access row, and the demand per cell code."""
    n = len(x["cells"])
    dem = demand.reindex(x["cells"]).fillna(0.0).to_numpy(float)
    denom = np.bincount(x["code"], w, n) + outside
    return w / denom[x["code"]] * dem[x["code"]], dem


def _by_lounge(x: dict, women: np.ndarray) -> pd.Series:
    """Women served per lounge that has access rows, by id (sorted, as a groupby)."""
    lj = x["sup"][x["lounge"]]
    u, inv = np.unique(lj, return_inverse=True)
    return pd.Series(np.bincount(inv, women[x["lounge"]], len(u)), index=pd.Index(x["ids"][u], name="id")).sort_index()


def _base(v3, a, closed, not_scored, minutes=BASE_MINUTES, cscale=1.0) -> tuple[pd.DataFrame, dict]:
    """The suppliers open in this scenario and their access rows as allocate arrays. Cached; rebuilt
    whenever _access or _competitors hand back a new table (their caches cleared), or the weight
    parameters change (a notebook sweeps them)."""
    acc, comp = _access(v3, a, not_scored), _competitors(v3, a)
    key = (id(v3), closed, not_scored, ALPHA, RATING_ELASTICITY, tuple(DECAY.items()), minutes, cscale)
    hit = _BASE.get(key)
    if hit and hit[0] is acc and hit[1] is comp:
        return hit[2], hit[3]
    if (minutes, cscale) != (BASE_MINUTES, 1.0):   # same rows as the baseline levels, new weights
        sup, x = _base(v3, a, closed, not_scored)
        x = {**x, "minutes": minutes, "w": _weights(x["ws"], x["band"], x["lounge"], minutes, cscale)}
    else:
        sup = _suppliers(v3, a, closed, not_scored)
        x = _arrays(acc[acc.id.isin(sup.id)], sup, minutes, cscale)
    _BASE[key] = (acc, comp, sup, x)
    return sup, x


_BASE: dict[tuple, tuple] = {}


def _allocate(x: dict, demand: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
    women, _ = _alloc(x, demand, x["w"], _outside(x["reviews"]))
    n, lo = len(x["cells"]), x["lounge"]
    cells = pd.DataFrame({"demand": demand})
    cells["served_lounges"] = pd.Series(np.bincount(x["code"][lo], women[lo], n), index=x["cells"])
    cells["served_competitors"] = pd.Series(np.bincount(x["code"][~lo], women[~lo], n), index=x["cells"])
    cells = cells.fillna(0.0)
    cells["unserved"] = cells.demand - cells.served_lounges - cells.served_competitors
    return cells, _by_lounge(x, women)


def allocate(demand: pd.Series, acc: pd.DataFrame, sup: pd.DataFrame, minutes: float = BASE_MINUTES,
             cscale: float = 1.0) -> tuple[pd.DataFrame, pd.Series]:
    """Per cell: demand, served_lounges, served_competitors, unserved; per lounge: women served."""
    return _allocate(_arrays(acc, sup, minutes, cscale), demand)


def served(v3, a, demand: pd.Series, closed=frozenset(), not_scored=frozenset(), leave_one_out: bool = True,
           minutes: float = BASE_MINUTES, cscale: float = 1.0) -> dict:
    """Served women per open lounge, unserved per cell, and per lounge the share of its served women
    its siblings absorb if it closes (leave-one-out; `leave_one_out=False` skips it: absorbed is {})."""
    sup, x = _base(v3, a, frozenset(closed), frozenset(not_scored), minutes, cscale)
    cells, by_lounge = _allocate(x, demand)
    absorbed = {}
    if not leave_one_out:
        return {"cells": cells, "served": by_lounge.to_dict(), "absorbed": absorbed}
    lounges = sup[sup.lounge].id.tolist()
    for b in lounges:
        mine = by_lounge.get(b, 0.0)
        if not mine:
            absorbed[b] = None
            continue
        # closing b = its rows out of every denominator, and b out of the outside option's percentile
        k = int(np.flatnonzero(x["ids"] == b)[0])
        women, _ = _alloc(x, demand, np.where(x["sup"] == k, 0.0, x["w"]), _outside(np.delete(x["reviews"], k)))
        after = _by_lounge(x, women)
        gain = sum(after.get(o, 0.0) - by_lounge.get(o, 0.0) for o in lounges if o != b)
        absorbed[b] = gain / mine
    return {"cells": cells, "served": by_lounge.to_dict(), "absorbed": absorbed}


def site_access(v3, a, lat: float, lng: float, not_scored=frozenset()) -> pd.DataFrame:
    """(cell_id, minutes) for every cell that reaches a point within 20 min: its own isochrone where
    fetched, else the fitted straight-line bands."""
    _access(v3, a, not_scored)
    km = _ACCESS[id(v3)][2]
    hit = _SITE_GEOM.get(id(v3))
    if not (hit and hit[0] is v3):
        iso, cells = _iso(v3), v3.cells
        other = cells[~cells.index.isin(iso)]
        _SITE_GEOM[id(v3)] = hit = (v3, list(iso), {b: np.array([p[b] for p in iso.values()], dtype=object) for b in BANDS},
                                    other.index, other.lat.to_numpy(float), other.lng.to_numpy(float))
    _, ids, polys, oid, olat, olng = hit
    inside = {b: shapely.contains_xy(polys[b], lng, lat) for b in BANDS}   # = poly.contains(Point(lng, lat))
    rows = []
    for i, cid in enumerate(ids):
        b = next((b for b in BANDS if inside[b][i]), None)
        if b:
            rows.append((cid, b))
    d = _km(lat, lng, olat, olng)
    for i in np.flatnonzero(d <= km[20]):
        rows.append((oid[i], next(b for b in BANDS if d[i] <= km[b])))
    return pd.DataFrame(rows, columns=["cell_id", "minutes"])


_SITE_GEOM: dict[int, tuple] = {}


_SITE_ACCESS: dict[tuple, tuple] = {}
_NEW: dict[tuple, tuple] = {}
_OPEN: dict[tuple, tuple] = {}


def _site_access(v3, a, lat, lng, not_scored) -> pd.DataFrame:
    """site_access, cached per V3 and point (it doesn't depend on the levels or closures)."""
    hit = _SITE_ACCESS.get((id(v3), lat, lng))
    if not (hit and hit[0] is v3):
        _SITE_ACCESS[(id(v3), lat, lng)] = hit = (v3, site_access(v3, a, lat, lng, not_scored))
    return hit[1]


def _new_site(x: dict, new: pd.DataFrame, lat: float, lng: float, reviews: float, rating: float | None,
              demand: pd.Series) -> dict:
    """A typical lounge "NEW" at (lat, lng), `new` its site_access. Per NEW access row: its weight, its
    cell's code in x (-1: a cell x doesn't reach), that cell's demand and NEW's total weight there."""
    key = (id(new), x["minutes"], reviews, rating)
    hit = _NEW.get(key)
    if not (hit and hit[0] is new):   # new is _site_access's cached table: one NEW per point and drive time
        _NEW[key] = hit = (new, _arrays(new.assign(id="NEW"), pd.DataFrame([{
            "id": "NEW", "lat": lat, "lng": lng, "reviews": reviews, "rating": rating, "lounge": True}]), x["minutes"]))
    y = hit[1]
    return {"w": y["w"], "code": x["cells"].get_indexer(y["cells"])[y["code"]],
            "dem": demand.reindex(y["cells"]).fillna(0.0).to_numpy(float)[y["code"]],
            "wcell": np.bincount(y["code"], y["w"], len(y["cells"]))[y["code"]], "reviews": y["reviews"]}


def _new_served(n: dict, other: np.ndarray, outside: float) -> float:
    """Women NEW serves; `other` is every other supplier's weight per x cell code."""
    rest = np.where(n["code"] >= 0, other[np.maximum(n["code"], 0)], 0.0) if len(other) else 0.0
    return float((n["w"] / (rest + n["wcell"] + outside) * n["dem"]).sum())


def what_if_open(v3, a, demand: pd.Series, lat: float, lng: float, reviews: float, rating: float | None,
                 closed=frozenset(), not_scored=frozenset(), minutes: float = BASE_MINUTES, cscale: float = 1.0) -> dict:
    """Open a typical lounge at (lat, lng): the women it would serve, and how many of them it takes
    from our existing lounges (the rest is new to the network). As allocate with NEW's rows appended,
    summed by cell: a cell's lounge women are its lounge weight x demand / its denominator."""
    _, x = _base(v3, a, frozenset(closed), frozenset(not_scored), minutes, cscale)
    n = _new_site(x, _site_access(v3, a, lat, lng, not_scored), lat, lng, reviews, rating, demand)
    hit = _OPEN.get((id(x), id(demand)))
    if not (hit and hit[0] is x and hit[1] is demand):   # once per scenario: every area shares it
        m, lo = len(x["cells"]), x["lounge"]
        total = np.bincount(x["code"], x["w"], m)
        ours = np.bincount(x["code"][lo], x["w"][lo], m) * demand.reindex(x["cells"]).fillna(0.0).to_numpy(float)
        _OPEN.clear()   # keeps the last scenario only
        _OPEN[(id(x), id(demand))] = hit = (x, demand, total, ours, (ours / (total + _outside(x["reviews"]))).sum())
    _, _, total, ours, before = hit
    inx = n["code"] >= 0
    added = np.bincount(n["code"][inx], n["w"][inx], len(total))
    out2 = _outside(np.append(x["reviews"], n["reviews"]))
    served = _new_served(n, total, out2)
    taken = float(before - (ours / (total + added + out2)).sum())
    return {"served": served, "taken_from_lounges": taken, "net_new": served - taken}


def site_served(v3, a, demand: pd.Series, reviews: float, rating: float | None,
                closed=frozenset(), not_scored=frozenset(), minutes: float = BASE_MINUTES,
                cscale: float = 1.0) -> dict[str, float]:
    """Per open scored lounge: the women a typical lounge (these reviews and rating) would serve at its
    site with that lounge closed and the rest open. Same as what_if_open(closed=closed | {b}), but only
    NEW's cells are touched: their denominators lose b's weight and gain NEW's."""
    sup, x = _base(v3, a, frozenset(closed), frozenset(not_scored), minutes, cscale)
    m = len(x["cells"])
    total = np.bincount(x["code"], x["w"], m)
    lo = np.flatnonzero(x["lounge"])
    out = {}
    for b, lat, lng in sup.loc[sup.lounge, ["id", "lat", "lng"]].itertuples(index=False):
        k = int(np.flatnonzero(x["ids"] == b)[0])
        rows = lo[x["sup"][lo] == k]
        n = _new_site(x, _site_access(v3, a, lat, lng, not_scored), lat, lng, reviews, rating, demand)
        other = total - np.bincount(x["code"][rows], x["w"][rows], m)
        out[b] = _new_served(n, other, _outside(np.delete(np.append(x["reviews"], n["reviews"]), k)))
    return out
