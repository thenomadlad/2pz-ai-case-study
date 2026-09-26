import math

from src.features.assign import assign_communities, haversine_km
from src.models import Branch, Community


def _branch(id, lat, lng):
    return Branch(id=id, name=id, lat=lat, lng=lng, area="x", rating=None,
                  review_count=None, avg_price_aed=None, source="seed")


def _community(id, lat, lng, female):
    return Community(id=id, name_en=id, lat=lat, lng=lng, population_total=female * 2,
                      population_female=female, is_estimated=False)


def test_haversine_known_distance():
    # Roughly Dubai Marina to Deira, ~25km
    d = haversine_km(25.0805, 55.1403, 25.2697, 55.3095)
    assert 20 < d < 30


def test_haversine_zero_for_same_point():
    assert haversine_km(25.0, 55.0, 25.0, 55.0) == 0.0


def test_assign_picks_nearest():
    branches = [_branch("near", 25.10, 55.20), _branch("far", 25.50, 55.50)]
    communities = [_community("c1", 25.11, 55.21, 1000)]

    result = assign_communities(branches, communities, contest_ratio=1.25)

    assert len(result) == 1
    assert result[0].nearest_branch_id == "near"
    assert result[0].second_branch_id == "far"
    assert result[0].female_pop == 1000


def test_assign_marks_contested_when_close():
    branches = [_branch("b1", 25.10, 55.20), _branch("b2", 25.101, 55.201)]
    communities = [_community("c1", 25.10, 55.20, 500)]

    result = assign_communities(branches, communities, contest_ratio=1.25)

    assert result[0].contested is True


def test_assign_not_contested_when_far_apart():
    branches = [_branch("b1", 25.10, 55.20), _branch("b2", 26.0, 56.0)]
    communities = [_community("c1", 25.10, 55.20, 500)]

    result = assign_communities(branches, communities, contest_ratio=1.25)

    assert result[0].contested is False


def test_assign_single_branch_has_no_second():
    branches = [_branch("only", 25.10, 55.20)]
    communities = [_community("c1", 25.11, 55.21, 500)]

    result = assign_communities(branches, communities, contest_ratio=1.25)

    assert result[0].second_branch_id is None
    assert result[0].second_km is None
    assert result[0].contested is False
