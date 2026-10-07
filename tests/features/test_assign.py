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
    communities = [_community("c1", 25.1005, 55.2005, 500)]

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


def test_assign_contested_when_tied_at_same_location():
    branches = [_branch("b1", 25.10, 55.20), _branch("b2", 25.10, 55.20)]
    communities = [_community("c1", 25.10, 55.20, 500)]

    result = assign_communities(branches, communities, contest_ratio=1.25)

    assert result[0].nearest_km == 0.0
    assert result[0].second_km == 0.0
    assert result[0].contested is True


def test_count_competitors_assigns_to_nearest_community_within_cutoff():
    from src.features.assign import count_competitors
    from src.models import Community, Competitor

    def comm(cid, lat):
        return Community(id=cid, name_en=cid, lat=lat, lng=55.0, population_total=1000,
                         population_female=None, is_estimated=True)

    def comp(cid, lat):
        return Competitor(id=cid, name=cid, category="beauty", lat=lat, lng=55.0)

    communities = [comm("north", 25.10), comm("south", 25.00)]
    # 0.01 deg lat ~ 1.1 km; 0.2 deg ~ 22 km, beyond the 3 km cutoff.
    competitors = [comp("k1", 25.09), comp("k2", 25.01), comp("k3", 25.011), comp("far", 25.30)]
    assert count_competitors(competitors, communities) == {"north": 1, "south": 2}
