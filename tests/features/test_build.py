import json

from src.features.build import build_features, main
from src.config import Settings
from src.models import Branch, Community


def _branch(id, lat, lng, price=100.0, rating=4.5, reviews=50):
    return Branch(id=id, name=id.title(), lat=lat, lng=lng, area="x", rating=rating,
                  review_count=reviews, avg_price_aed=price, source="seed")


def _community(id, lat, lng, female, is_estimated=False):
    return Community(id=id, name_en=id, lat=lat, lng=lng, population_total=female * 2,
                      population_female=female, is_estimated=is_estimated)


def test_build_features_basic():
    branches = [_branch("a", 25.10, 55.20), _branch("b", 25.50, 55.50)]
    communities = [_community("c1", 25.11, 55.21, 1000), _community("c2", 25.51, 55.51, 500)]

    features, network, assignments = build_features(branches, communities, price_flags=["b"],
                                        contest_ratio=1.25)

    by_id = {f.branch_id: f for f in features}
    assert by_id["a"].female_pop_served == 1000
    assert by_id["a"].communities_served == 1
    assert by_id["b"].estimated_fields == ["avg_price_aed"]
    assert network.branch_count == 2
    assert network.total_female_population == 1500
    assert len(assignments) == 2


def test_build_features_flags_female_pop_served_when_any_served_community_estimated():
    # Branch "a" is served by one estimated and one reported community -> flagged.
    # Branch "b" is served only by reported communities -> not flagged.
    branches = [_branch("a", 25.10, 55.20), _branch("b", 25.50, 55.50)]
    communities = [
        _community("c1", 25.101, 55.201, 1000, is_estimated=True),
        _community("c2", 25.099, 55.199, 500, is_estimated=False),
        _community("c3", 25.501, 55.501, 700, is_estimated=False),
    ]

    features, _, _ = build_features(branches, communities, price_flags=[], contest_ratio=1.25)
    by_id = {f.branch_id: f for f in features}

    assert "female_pop_served" in by_id["a"].estimated_fields
    assert "female_pop_served" not in by_id["b"].estimated_fields


def test_build_features_branch_serving_zero_communities_does_not_crash():
    # A branch with no communities assigned to it (all communities are closer to another
    # branch) should get zero-valued distance/pop fields rather than crashing, per the
    # `if served: ... else: mean_distance, max_distance = 0.0, 0.0` branch in build_features.
    branches = [_branch("a", 25.10, 55.20), _branch("b", 25.50, 55.50)]
    # Both communities are far closer to "b" than "a", so "a" serves zero communities.
    communities = [
        _community("c1", 25.501, 55.501, 1000),
        _community("c2", 25.499, 55.499, 500),
    ]

    features, network, assignments = build_features(branches, communities, price_flags=[],
                                                      contest_ratio=1.25)
    by_id = {f.branch_id: f for f in features}

    assert by_id["a"].communities_served == 0
    assert by_id["a"].female_pop_served == 0
    assert by_id["a"].mean_distance_km == 0.0
    assert by_id["a"].max_distance_km == 0.0
    assert by_id["a"].contested_share == 0.0
    assert by_id["a"].estimated_fields == []
    assert network.branch_count == 2


def test_main_writes_processed_files(tmp_path):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    raw_dir.mkdir()
    processed_dir.mkdir()

    (raw_dir / "branches.json").write_text(json.dumps([
        _branch("a", 25.10, 55.20).model_dump(),
    ]))
    (raw_dir / "price_flags.json").write_text(json.dumps([]))
    (raw_dir / "communities.json").write_text(json.dumps([
        _community("c1", 25.11, 55.21, 1000).model_dump(),
    ]))

    settings = Settings(_env_file=None, raw_dir=raw_dir, processed_dir=processed_dir)
    main(settings)

    features_out = json.loads((processed_dir / "branch_features.json").read_text())
    assignment_out = json.loads((processed_dir / "community_assignment.json").read_text())
    communities_out = json.loads((processed_dir / "communities.json").read_text())
    assert "network" in features_out
    assert len(features_out["branches"]) == 1
    assert len(assignment_out) == 1
    assert len(communities_out) == 1
