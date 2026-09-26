import json

from src.features.build import build_features, main
from src.config import Settings
from src.models import Branch, Community


def _branch(id, lat, lng, price=100.0, rating=4.5, reviews=50):
    return Branch(id=id, name=id.title(), lat=lat, lng=lng, area="x", rating=rating,
                  review_count=reviews, avg_price_aed=price, source="seed")


def _community(id, lat, lng, female):
    return Community(id=id, name_en=id, lat=lat, lng=lng, population_total=female * 2,
                      population_female=female, is_estimated=False)


def test_build_features_basic():
    branches = [_branch("a", 25.10, 55.20), _branch("b", 25.50, 55.50)]
    communities = [_community("c1", 25.11, 55.21, 1000), _community("c2", 25.51, 55.51, 500)]

    features, network = build_features(branches, communities, price_flags=["b"],
                                        contest_ratio=1.25)

    by_id = {f.branch_id: f for f in features}
    assert by_id["a"].female_pop_served == 1000
    assert by_id["a"].communities_served == 1
    assert by_id["b"].estimated_fields == ["avg_price_aed"]
    assert network.branch_count == 2
    assert network.total_female_population == 1500


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
