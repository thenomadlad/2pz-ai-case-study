from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict


class BaselineAssumptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contest_ratio: float = 1.25
    global_female_share: float = 0.49
    fallback_price_aed: float = 99.0
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


class Branch(BaseModel):
    # extra="forbid" so a typo'd override field (e.g. scenario patch) raises loudly at
    # validation instead of silently no-opping -- see src/scenario/apply.py.
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    lat: float
    lng: float
    area: str
    rating: float | None
    review_count: int | None
    avg_price_aed: float | None
    source: Literal["seed", "fresha", "places", "scenario"]


class Community(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name_en: str
    lat: float
    lng: float
    population_total: int
    population_female: int | None
    is_estimated: bool


class Competitor(BaseModel):
    """A non-Bedashing beauty/hair salon from OSM -- see scripts/fetch_competitors.py."""
    id: str
    name: str
    category: str
    lat: float
    lng: float


class CommunityAssignment(BaseModel):
    community_id: str
    nearest_branch_id: str
    nearest_km: float
    second_branch_id: str | None
    second_km: float | None
    contested: bool
    female_pop: int


class BranchFeatures(BaseModel):
    branch_id: str
    name: str
    lat: float
    lng: float
    female_pop_served: int
    communities_served: int
    mean_distance_km: float
    max_distance_km: float
    contested_pop: int
    contested_share: float
    nearest_sibling_km: float
    siblings_within_5km: int
    avg_price_aed: float
    price_index: float
    rating: float | None
    review_count: int | None
    pop_per_1k_rank: int
    estimated_fields: list[str]
    # Competitive overlap: competitors in this branch's catchment communities.
    competitors_in_catchment: int = 0
    competitors_per_10k: float = 0.0


class CommunityFeatures(BaseModel):
    community_id: str
    name: str
    lat: float
    lng: float
    female_pop: int
    competitors: int
    competitors_per_10k: float
    nearest_branch_id: str
    nearest_branch_km: float
    nearest_branch_pop_served: int
    hosts_branch: bool
    branches_here: int = 0  # Bedashing branches whose nearest community centroid this is


class NetworkStats(BaseModel):
    branch_count: int
    total_female_population: int
    female_pop_served_median: float
    female_pop_served_p25: float
    female_pop_served_p75: float
    contested_share_median: float
    contested_share_p25: float
    contested_share_p75: float
    avg_price_aed_median: float
    avg_price_aed_p25: float
    avg_price_aed_p75: float
    rating_median: float | None
    rating_p25: float | None
    rating_p75: float | None


class Decision(BaseModel):
    branch_id: str
    action: Literal["PROTECT", "HOLD", "SHRINK"]
    confidence: Literal["low", "medium", "high"]
    rationale: str
    key_drivers: list[str]
    caveats: list[str]
    composite: float = 0.0
    # Per-signal score on its fixed 0-1 scale (1 = good for the branch).
    scores: dict[str, float] = {}


class OpportunityDecision(BaseModel):
    community_id: str
    action: Literal["GROW", "WATCH", "SKIP"]
    underserved: bool
    unsaturated: bool
    rationale: str
    caveats: list[str]
    # What's left in this area, shown on its page and cited by its explanation.
    salons_supported: float = 0.0   # at the Dubai median density
    salon_headroom: int = 0         # salons supported minus salons already here
    uncovered_women: int = 0        # women whose nearest Bedashing branch is beyond the line
    fair_share: float = 0.0         # Bedashing's share of the salons here (naive capture)
    captured_women_est: int = 0     # fair share x women


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
    kind: Literal["branch", "opportunity", "network"]
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


class LoungeFeatures(BaseModel):
    branch_id: str
    name: str
    emirate: str
    lat: float
    lng: float
    rating: float | None
    review_count: int
    catchment_women: float          # women 15+ in its catchment cells
    catchment_cells: int
    shared_share: float             # share of those women in cells another open lounge also reaches
    capture: float                  # capture_by_coverage
    substitutes_k: int
    recall_multiplier: float
    premium_pool: int               # premium salons in its catchment
    thin_premium_market: bool       # premium_pool < THIN_MARKET
    substitutes_median_rating: float | None
    rating_gap: float | None        # rating - substitutes_median_rating
    est_customers: float            # capture x catchment_women (0 if not scored)
    not_scored: bool                # the airport lounge


class Area(BaseModel):
    """A growth candidate: a contiguous piece of populated cells no open lounge reaches."""
    area_id: str
    name: str
    emirate: str
    lat: float
    lng: float
    women: float
    cells: int
    worker_share: float
    premium_salons: int | None              # over covered cells; None = none covered
    premium_reviews_per_1k: float | None
    full_circle_share: float | None
    data_coverage: float                    # share of the area's women in cells with competitor data
    cell_ids: list[str]
    nearest_lounge_id: str                  # straight-line, among open lounges
    nearest_lounge_km: float
