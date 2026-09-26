from typing import Literal, Protocol

from pydantic import BaseModel


class Branch(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    area: str
    rating: float | None
    review_count: int | None
    avg_price_aed: float | None
    source: Literal["seed", "fresha", "places"]


class Community(BaseModel):
    id: str
    name_en: str
    lat: float
    lng: float
    population_total: int
    population_female: int | None
    is_estimated: bool


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


class DecisionModel(Protocol):
    name: str

    def decide(self, branch: BranchFeatures, network: NetworkStats) -> Decision: ...
