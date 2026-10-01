from src.models import BranchFeatures, CommunityAssignment, Decision
from src.scenario.models import BranchDiffEntry, CommunityDiffEntry


def _merge(features: BranchFeatures, decision: Decision | None) -> dict:
    merged = features.model_dump()
    if decision is not None:
        merged.update(decision.model_dump())
    return merged


def compute_branch_diff(
    baseline_features: list[BranchFeatures], baseline_decisions: list[Decision],
    current_features: list[BranchFeatures], current_decisions: list[Decision],
) -> list[BranchDiffEntry]:
    baseline_features_by_id = {f.branch_id: f for f in baseline_features}
    current_features_by_id = {f.branch_id: f for f in current_features}
    baseline_decisions_by_id = {d.branch_id: d for d in baseline_decisions}
    current_decisions_by_id = {d.branch_id: d for d in current_decisions}

    entries = []
    for branch_id in sorted(set(baseline_features_by_id) | set(current_features_by_id)):
        old_features = baseline_features_by_id.get(branch_id)
        new_features = current_features_by_id.get(branch_id)
        old = _merge(old_features, baseline_decisions_by_id.get(branch_id)) if old_features else None
        new = _merge(new_features, current_decisions_by_id.get(branch_id)) if new_features else None

        changed_fields: dict[str, dict] = {}
        if old_features is not None and new_features is not None:
            for field in BranchFeatures.model_fields:
                if field == "branch_id":
                    continue
                old_val = getattr(old_features, field)
                new_val = getattr(new_features, field)
                if old_val != new_val:
                    changed_fields[field] = {"old": old_val, "new": new_val}

        old_action = old.get("action") if old else None
        new_action = new.get("action") if new else None

        entries.append(BranchDiffEntry(
            branch_id=branch_id, old=old, new=new,
            changed_fields=changed_fields, action_changed=old_action != new_action,
        ))
    return entries


def compute_community_diff(
    baseline_assignments: list[CommunityAssignment], current_assignments: list[CommunityAssignment],
) -> list[CommunityDiffEntry]:
    baseline_by_id = {a.community_id: a for a in baseline_assignments}
    current_by_id = {a.community_id: a for a in current_assignments}

    entries = []
    for community_id in sorted(set(baseline_by_id) | set(current_by_id)):
        old = baseline_by_id.get(community_id)
        new = current_by_id.get(community_id)
        old_branch_id = old.nearest_branch_id if old else None
        new_branch_id = new.nearest_branch_id if new else None
        entries.append(CommunityDiffEntry(
            community_id=community_id,
            reassigned=old_branch_id != new_branch_id,
            old_branch_id=old_branch_id,
            new_branch_id=new_branch_id,
        ))
    return entries
