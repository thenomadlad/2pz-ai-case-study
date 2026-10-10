from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict


class BaselineAssumptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Drive time a customer will travel to a salon; sources in data/seed/v3/SOURCES.md.
    travel_time_minutes: dict[str, int] = {"low": 10, "medium": 15, "high": 20}
    # Departure time for traffic-aware isochrones (Mapbox driving-traffic), local time.
    isochrone_depart_at: str = "2026-10-13T12:00"
    # Competitors: top-k premium substitutes per lounge. See SOURCES.md, "Competitors".
    bedashing_price_level: str = "expensive"
    comparable_price_levels: list[str] = ["expensive", "very_expensive"]
    premium_min_rating: float = 4.3
    competitor_coverage: dict[str, float] = {"low": 0.5, "medium": 0.6, "high": 0.7}
    search_recall: float = 0.66
    # Female share of adults in worker housing (OSM industrial land use); calibrated on
    # Dubai Statistics Center labour-camp communities. See SOURCES.md, "Market size".
    worker_housing_female_share: dict[str, float] = {"low": 0.01, "medium": 0.055, "high": 0.15}
    # How strongly demand follows a cell's observed median rent (Dubai only; elsewhere neutral).
    # See SOURCES.md, "Affluence".
    affluence_elasticity: dict[str, float] = {"low": 0.0, "medium": 0.5, "high": 1.0}
















class Decision(BaseModel):
    branch_id: str
    action: Literal["PROTECT", "HOLD", "SHRINK", "NOT SCORED"]
    confidence: Literal["low", "medium", "high"]
    rationale: str
    key_drivers: list[str]
    caveats: list[str]
    composite: float = 0.0
    # Per-signal score on its fixed 0-1 scale (1 = good for the branch).
    scores: dict[str, float] = {}




class AreaDecision(BaseModel):
    """A growth area's call: GROW / WATCH / SKIP (src/model/growth.py)."""
    area_id: str
    action: Literal["GROW", "WATCH", "SKIP"]
    big_enough: bool
    unsaturated: bool | None        # None: no competitor data
    rationale: str
    caveats: list[str]


class Evidence(BaseModel):
    field: str
    label: str
    value: float | int | str | bool | None


class Reason(BaseModel):
    # Which ranked argument this is (e.g. "cannibalisation"), set by src/explain.prioritize.
    topic: str = ""
    claim: str
    evidence: list[Evidence]


class Explanation(BaseModel):
    subject_id: str
    kind: Literal["lounge", "area", "uae"]
    action: str
    # The answer, in one sentence: the top of the pyramid.
    headline: str = ""
    reasons: list[Reason]
    # Plain-language caption for the factor table shown next to this decision.
    table_caption: str
    thresholds_note: str
    source: Literal["ai", "template"]


class Lounge(BaseModel):
    """A Bedashing lounge from data/seed/v3/branches.csv."""
    branch_id: str
    title: str
    name: str
    emirate: str
    lat: float
    lng: float
    place_id: str
    rating: float | None
    review_count: int
    address: str


@dataclass(frozen=True)
class Levels:
    """Assumption level names ("low"/"medium"/"high"); the values live in baseline.yaml."""
    travel: str = "medium"          # travel_time_minutes
    coverage: str = "medium"        # competitor_coverage
    worker_share: str = "medium"    # worker_housing_female_share
    affluence: str = "medium"       # affluence_elasticity


class LoungeFeatures(BaseModel):
    branch_id: str
    name: str
    emirate: str
    lat: float
    lng: float
    rating: float | None
    review_count: int
    catchment_women: float          # women 15+ in its catchment cells (raw)
    addressable_women: float        # catchment women x affluence weight: the demand signal
    affluence_rent: float | None    # women-weighted median observed rent (AED/yr); None: no observed cell
    affluence_coverage: float       # share of catchment women in cells with an observed rent
    catchment_cells: int
    shared_share: float             # share of those women in cells another open lounge also reaches
    capture: float                  # capture_by_coverage
    substitutes_k: int
    recall_multiplier: float
    premium_pool: int               # premium salons in its catchment
    thin_premium_market: bool       # premium_pool < THIN_MARKET
    substitutes_median_rating: float | None
    rating_gap: float | None        # rating - substitutes_median_rating
    est_customers: float            # capture x addressable_women (0 if not scored)
    not_scored: bool                # the airport lounge


class Area(BaseModel):
    """A growth candidate: a contiguous piece of populated cells no open lounge reaches."""
    area_id: str
    name: str
    emirate: str
    lat: float
    lng: float
    women: float
    addressable_women: float                # women x affluence weight: the size test
    affluence_rent: float | None            # women-weighted median observed rent; None: none observed
    affluence_coverage: float               # share of the area's women in cells with an observed rent
    cells: int
    worker_share: float
    premium_salons: int | None              # over covered cells; None = none covered
    premium_reviews_per_1k: float | None
    full_circle_share: float | None
    data_coverage: float                    # share of the area's women in cells with competitor data
    cell_ids: list[str]
    nearest_lounge_id: str                  # straight-line, among open lounges
    nearest_lounge_km: float
