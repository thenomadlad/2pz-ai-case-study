from typing import Protocol

from src.models import BranchFeatures, Decision, NetworkStats


class DecisionModel(Protocol):
    name: str

    def decide(self, branches: list[BranchFeatures], network: NetworkStats) -> list[Decision]: ...
