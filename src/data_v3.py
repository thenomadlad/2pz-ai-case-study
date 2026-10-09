"""The v3 data (data/seed/v3), loaded once: tables, polygons, and per-level competition.

Candidates and full shares are precomputed per level by `scripts/fetch_salons.py pool`."""
import json
from dataclasses import dataclass
from functools import lru_cache

import pandas as pd

from src.config import Settings
from src.config import settings as default_settings
from src.models import Lounge

LEVELS = ("low", "medium", "high")


@dataclass(frozen=True)
class V3:
    lounges: list[Lounge]
    cells: pd.DataFrame                      # indexed by cell_id
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


@lru_cache(maxsize=None)
def load_v3(settings: Settings | None = None) -> V3:
    d = (settings or default_settings).v3_dir
    lounges = _lounges(d / "branches.csv")
    polygons = {(f["properties"]["branch_id"], f["properties"]["minutes"]): f["geometry"]
                for f in json.load(open(d / "lounge_isochrones.geojson"))["features"]}
    salons = _salons(d / "salons.csv")
    rows = salons.reset_index().set_index("place_id", drop=False).to_dict("index")
    candidates = {(lo.branch_id, lv): [] for lo in lounges for lv in LEVELS}
    for r in pd.read_csv(d / "lounge_candidates_by_level.csv").itertuples():
        candidates[(r.branch_id, r.level)].append(rows[r.place_id])
    sat = pd.read_csv(d / "lounge_search_saturation_by_level.csv")
    full_share = {(r.branch_id, r.level): float(r.full_share) for r in sat.itertuples()}
    return V3(lounges, pd.read_csv(d / "cells.csv").set_index("cell_id"),
              pd.read_csv(d / "emirates.csv").set_index("emirate"), pd.read_csv(d / "catchment_cells.csv"),
              salons, pd.read_csv(d / "search_circles.csv"), polygons, candidates, full_share)
