"""The baseline and what-ifs, in memory: one cached run of the v3 pipeline per scenario."""
from functools import lru_cache

from pydantic import BaseModel

from src.config import REPO_ROOT, load_baseline_assumptions
from src.data_v3 import load_v3
from src.features.lounges import NOT_SCORED, build
from src.model import growth, scorecard
from src.models import Area, AreaDecision, Decision, Levels, LoungeFeatures


class Run(BaseModel):
    levels: Levels
    closed: list[str]
    features: list[LoungeFeatures]
    decisions: list[Decision]
    areas: list[Area]
    area_decisions: list[AreaDecision]
    flips: dict[str, int]           # per lounge: level combinations (of 81) that change its action


@lru_cache(maxsize=64)
def _run(levels: Levels, closed: frozenset[str], search_recall: float | None) -> Run:
    """Features, decisions (with level-sensitivity confidence) and growth areas for one scenario."""
    v3 = load_v3()
    ids = {lo.branch_id for lo in v3.lounges}
    if closed - ids:
        raise ValueError(f"unknown lounge id(s) in closed: {sorted(closed - ids)}; valid: {sorted(ids)}")
    if not ids - closed - set(NOT_SCORED):
        raise ValueError("closing every scored lounge leaves nothing to compare")
    a = load_baseline_assumptions(REPO_ROOT / "data" / "scenarios" / "baseline.yaml")
    if search_recall is not None:
        a = a.model_copy(update={"search_recall": search_recall})
    features, areas = build(v3, a, levels, closed)
    flips = scorecard.level_flips(v3, a, levels, closed)
    return Run(levels=levels, closed=sorted(closed), features=features,
               decisions=scorecard.decide(features, flips), flips=flips, areas=areas, area_decisions=growth.classify_all(areas))


def run(levels: Levels = Levels(), closed: frozenset[str] = frozenset(),  # noqa: B008 (frozen)
        search_recall: float | None = None) -> Run:
    """A deep copy of the cached run, so callers can mutate it freely."""
    return _run(levels, frozenset(closed), search_recall).model_copy(deep=True)


class LoungeChange(BaseModel):
    branch_id: str
    old_action: str | None
    new_action: str | None          # None: closed
    old_composite: float | None
    new_composite: float | None
    old_scores: dict[str, float]
    new_scores: dict[str, float]


class AreaChange(BaseModel):
    area_id: str
    old_action: str
    new_action: str


class RunDiff(BaseModel):
    lounges: list[LoungeChange] = []
    areas_appeared: list[str] = []
    areas_disappeared: list[str] = []
    areas_changed: list[AreaChange] = []

    @property
    def empty(self) -> bool:
        return not (self.lounges or self.areas_appeared or self.areas_disappeared or self.areas_changed)


def diff(before: Run, after: Run) -> RunDiff:
    """What changed from `before` to `after`: lounges whose call or signals moved, growth areas."""
    old = {d.branch_id: d for d in before.decisions}
    new = {d.branch_id: d for d in after.decisions}
    lounges = []
    for b in old.keys() | new.keys():
        o, n = old.get(b), new.get(b)
        if o and n and (o.action, o.composite, o.scores) == (n.action, n.composite, n.scores):
            continue
        lounges.append(LoungeChange(
            branch_id=b, old_action=o and o.action, new_action=n and n.action,
            old_composite=o and o.composite, new_composite=n and n.composite,
            old_scores=o.scores if o else {}, new_scores=n.scores if n else {}))
    oa = {d.area_id: d.action for d in before.area_decisions}
    na = {d.area_id: d.action for d in after.area_decisions}
    return RunDiff(
        lounges=sorted(lounges, key=lambda c: c.branch_id),
        areas_appeared=sorted(na.keys() - oa.keys()), areas_disappeared=sorted(oa.keys() - na.keys()),
        areas_changed=[AreaChange(area_id=i, old_action=oa[i], new_action=na[i])
                       for i in sorted(oa.keys() & na.keys()) if oa[i] != na[i]])
