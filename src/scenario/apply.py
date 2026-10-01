from src.models import Branch, Community

_BRANCH_NEW_DEFAULTS = {
    "rating": None, "review_count": None, "avg_price_aed": None, "source": "scenario",
}
_COMMUNITY_NEW_DEFAULTS = {"population_female": None, "is_estimated": False}


def apply_branch_overrides(branches: list[Branch], overrides: dict[str, dict]) -> list[Branch]:
    by_id = {b.id: i for i, b in enumerate(branches)}
    result = list(branches)
    for branch_id, patch in overrides.items():
        if branch_id in by_id:
            idx = by_id[branch_id]
            # Re-validate the merged dict (not model_copy(update=patch), which skips
            # validation entirely) so a typo'd field name or a type-mismatched value raises
            # loudly here instead of silently no-opping or blowing up later deep inside
            # unrelated code (e.g. haversine math on a string lat).
            result[idx] = Branch.model_validate({**result[idx].model_dump(), **patch})
        else:
            result.append(Branch(id=branch_id, **{**_BRANCH_NEW_DEFAULTS, **patch}))
    return result


def apply_community_overrides(
    communities: list[Community], overrides: dict[str, dict],
) -> list[Community]:
    by_id = {c.id: i for i, c in enumerate(communities)}
    result = list(communities)
    for community_id, patch in overrides.items():
        if community_id in by_id:
            idx = by_id[community_id]
            result[idx] = Community.model_validate({**result[idx].model_dump(), **patch})
        else:
            result.append(Community(id=community_id, **{**_COMMUNITY_NEW_DEFAULTS, **patch}))
    return result
