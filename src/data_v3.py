"""The v3 data (data/seed/v3), loaded once: tables, polygons, and per-level competition.

Candidates and full shares are precomputed per level by `scripts/fetch_salons.py pool`."""
import json
import re
import unicodedata
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pandas as pd

from src.config import Settings
from src.config import settings as default_settings
from src.models import Lounge

LEVELS = ("low", "medium", "high")


@dataclass(frozen=True)
class V3:
    lounges: list[Lounge]
    cells: pd.DataFrame                      # indexed by cell_id; with rent_observed, affluence_source
    emirates: pd.DataFrame                   # indexed by emirate
    catchment: pd.DataFrame                  # cell_id, level, branch_id
    salons: pd.DataFrame                     # the full pool, indexed by place_id; no NaN in market fields
    circles: pd.DataFrame                    # search_circles.csv (both runs)
    polygons: dict[tuple[str, int], dict]    # (branch_id, minutes) -> GeoJSON geometry
    candidates: dict[tuple[str, str], list[dict]]   # (branch_id, level) -> non-excluded salons in the polygon
    full_share: dict[tuple[str, str], float]        # (branch_id, level) -> share of circles that came back full


def _salons(path) -> pd.DataFrame:
    s = pd.read_csv(path, dtype={"price_level": str, "excluded_reason": str}).set_index("place_id")
    s["review_count"] = s.review_count.fillna(0).astype(int)
    s["rating"] = s.rating.astype(object).where(s.rating.notna(), None)
    s["price_level"] = s.price_level.fillna("")
    s["excluded_reason"] = s.excluded_reason.fillna("")
    return s


def _lounges(path) -> list[Lounge]:
    df = pd.read_csv(path)
    df["rating"] = df.rating.astype(object).where(df.rating.notna(), None)
    return [Lounge(**r) for r in df[list(Lounge.model_fields)].to_dict("records")]


ADREC_SPELLINGS = {"ghiyathi": "ghayathi"}   # OSM spelling -> ADREC spelling, after normalising
SHOP_RENT_WHY = (
    "Shop rent (AED/m2/yr, our site cost) per cell, one column for every emirate, 2026-10-11. Dubai: DLD "
    "Ejari shop contracts (cell_shop_rent.csv). Abu Dhabi: ADREC 2025 street-retail contract rates by "
    "district (adrec_retail_rent_2025.csv), matched on the cell's OSM name. Northern emirates: median "
    "asking rent of nearby shop listings (cell_listing_rent.csv; asking, so above achieved rents). A cell "
    "with none of these (or a listings cell with under 5 listings near it) takes its emirate's median "
    "over the cells that have one: source emirate_median.")


def _norm(name: str) -> str:
    """District key: ASCII, lowercase, no punctuation or 'al', no spaces (Mzeer'ah = Mzeerʻah)."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]+", "", s.replace("-", " "))
    s = re.sub(r"\bal\b", "", s)
    s = re.sub(r"\s+", "", s)
    return ADREC_SPELLINGS.get(s, s)


def _adrec(d: Path, cells: pd.DataFrame) -> pd.Series:
    """ADREC district rent per Abu Dhabi cell by name; Al Bateen and Al Rawdah exist in both Abu Dhabi
    City and Al Ain City, told apart by longitude (Al Ain lies east of 55E)."""
    ad = pd.read_csv(d / "adrec_retail_rent_2025.csv")
    ad["key"] = ad.district.map(_norm)
    rate = ad.set_index(["key", "municipality"]).rent_aed_sqm
    by_key = ad.groupby("key").rent_aed_sqm.first()
    dup = set(ad.key[ad.key.duplicated()])
    out = {}
    for cid, c in cells[cells.emirate == "Abu Dhabi"].iterrows():
        k = _norm(c["name"])
        if k in dup:
            out[cid] = rate[(k, "Al Ain City" if c.lng > 55 else "Abu Dhabi City")]
        elif k in by_key.index:
            out[cid] = by_key[k]
    return pd.Series(out, dtype=float)


def _cells(d: Path) -> pd.DataFrame:
    """cells.csv joined with cell_affluence.csv: rent_observed (AED/yr, NaN outside the observed
    Dubai cells) and affluence_source (observed | none); and shop_rent_m2 / shop_rent_source
    (dld | adrec | listings | emirate_median; SHOP_RENT_WHY)."""
    aff = pd.read_csv(d / "cell_affluence.csv").set_index("cell_id")
    cells = pd.read_csv(d / "cells.csv").set_index("cell_id")
    cells = cells.join(aff[["rent_observed"]]).join(aff.source.rename("affluence_source"))
    cells["affluence_source"] = cells.affluence_source.fillna("none")
    rent, source = pd.Series(float("nan"), index=cells.index), pd.Series("", index=cells.index)
    parts = []
    if (d / "cell_shop_rent.csv").exists():
        parts.append(("dld", pd.read_csv(d / "cell_shop_rent.csv").set_index("cell_id").shop_rent_m2))
    if (d / "adrec_retail_rent_2025.csv").exists():
        parts.append(("adrec", _adrec(d, cells)))
    if (d / "cell_listing_rent.csv").exists():
        lr = pd.read_csv(d / "cell_listing_rent.csv").set_index("cell_id")
        parts.append(("listings", lr.listing_rent_m2[~lr.fallback.astype(bool)]))
    for name, s in parts:
        s = s.reindex(cells.index)
        fill = rent.isna() & s.notna()
        rent[fill], source[fill] = s[fill], name
    em = rent.groupby(cells.emirate).median()
    gap = rent.isna() & cells.emirate.map(em).notna()
    rent[gap], source[gap] = cells.emirate[gap].map(em), "emirate_median"
    cells["shop_rent_m2"], cells["shop_rent_source"] = rent, source.where(rent.notna(), "none")
    return cells


def load_v3(settings: Settings | None = None) -> V3:
    return _load((settings or default_settings).v3_dir)


@cache
def _load(d: Path) -> V3:       # cached on the directory: Settings is unhashable
    lounges = _lounges(d / "branches.csv")
    polygons = {(f["properties"]["branch_id"], f["properties"]["minutes"]): f["geometry"]
                for f in json.loads((d / "lounge_isochrones.geojson").read_text())["features"]}
    salons = _salons(d / "salons.csv")
    rows = salons.reset_index().set_index("place_id", drop=False).to_dict("index")
    candidates = {(lo.branch_id, lv): [] for lo in lounges for lv in LEVELS}
    for r in pd.read_csv(d / "lounge_candidates_by_level.csv").itertuples():
        candidates[(r.branch_id, r.level)].append(rows[r.place_id])
    sat = pd.read_csv(d / "lounge_search_saturation_by_level.csv")
    full_share = {(r.branch_id, r.level): float(r.full_share) for r in sat.itertuples()}
    return V3(lounges, _cells(d),
              pd.read_csv(d / "emirates.csv").set_index("emirate"), pd.read_csv(d / "catchment_cells.csv"),
              salons, pd.read_csv(d / "search_circles.csv"), polygons, candidates, full_share)
# retail_rent_bands.csv / lounge_site_class.csv (JLL mall bands) stay in the repo, unused since 2026-10-11:
# every cell now has a shop rent (SHOP_RENT_WHY).
