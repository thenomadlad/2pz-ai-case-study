import pytest
from pydantic import ValidationError

from src.models import Branch, Community
from src.scenario.apply import apply_branch_overrides, apply_community_overrides


def _branch(id_, lat=25.0, lng=55.0, rating=4.5):
    return Branch(id=id_, name=f"Branch {id_}", lat=lat, lng=lng, area="Area",
                  rating=rating, review_count=100, avg_price_aed=99.0, source="seed")


def _community(id_, population_total=1000, population_female=490):
    return Community(id=id_, name_en=f"Community {id_}", lat=25.0, lng=55.0,
                      population_total=population_total, population_female=population_female,
                      is_estimated=False)


def test_patch_existing_branch_only_changes_given_fields():
    branches = [_branch("a", rating=4.5), _branch("b", rating=4.0)]
    result = apply_branch_overrides(branches, {"a": {"rating": 4.9}})

    by_id = {b.id: b for b in result}
    assert by_id["a"].rating == 4.9
    assert by_id["a"].lat == 25.0  # unchanged
    assert by_id["b"].rating == 4.0  # untouched


def test_patch_existing_branch_location():
    branches = [_branch("a", lat=25.0, lng=55.0)]
    result = apply_branch_overrides(branches, {"a": {"lat": 25.27, "lng": 55.31}})

    assert result[0].lat == 25.27
    assert result[0].lng == 55.31


def test_new_branch_inserted_with_defaults():
    branches = [_branch("a")]
    result = apply_branch_overrides(branches, {
        "new-one": {"name": "New One", "lat": 25.1, "lng": 55.1, "area": "Somewhere"},
    })

    assert len(result) == 2
    new_branch = next(b for b in result if b.id == "new-one")
    assert new_branch.name == "New One"
    assert new_branch.rating is None  # defaulted
    assert new_branch.source == "scenario"  # defaulted


def test_new_branch_missing_required_field_raises():
    branches = [_branch("a")]
    with pytest.raises(ValidationError):
        apply_branch_overrides(branches, {"new-one": {"rating": 4.9}})  # no name/lat/lng/area


def test_patch_existing_community():
    communities = [_community("c1", population_female=490)]
    result = apply_community_overrides(communities, {"c1": {"population_female": 9000}})

    assert result[0].population_female == 9000
    assert result[0].is_estimated is False  # unchanged


def test_new_community_inserted_with_defaults():
    communities = [_community("c1")]
    result = apply_community_overrides(communities, {
        "new-c": {"name_en": "New Community", "lat": 25.1, "lng": 55.1, "population_total": 5000},
    })

    assert len(result) == 2
    new_community = next(c for c in result if c.id == "new-c")
    assert new_community.population_female is None
    assert new_community.is_estimated is False
