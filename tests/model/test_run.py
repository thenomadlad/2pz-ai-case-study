import json

from src.config import Settings
from src.model.run import main, resolve_backend
from src.model.rubric import RubricModel


def test_resolve_backend_falls_back_without_api_key():
    settings = Settings(_env_file=None, model_backend="llm", anthropic_api_key=None)
    model = resolve_backend(settings)
    assert isinstance(model, RubricModel)


def test_resolve_backend_honors_explicit_rubric():
    settings = Settings(_env_file=None, model_backend="rubric")
    model = resolve_backend(settings)
    assert isinstance(model, RubricModel)


def test_main_writes_decisions(tmp_path):
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    (processed_dir / "branch_features.json").write_text(json.dumps({
        "network": {
            "branch_count": 1, "total_female_population": 1000,
            "female_pop_served_median": 1000, "female_pop_served_p25": 1000,
            "female_pop_served_p75": 1000, "contested_share_median": 0.1,
            "contested_share_p25": 0.1, "contested_share_p75": 0.1,
            "avg_price_aed_median": 100, "avg_price_aed_p25": 100, "avg_price_aed_p75": 100,
            "rating_median": 4.5, "rating_p25": 4.5, "rating_p75": 4.5,
        },
        "branches": [{
            "branch_id": "a", "name": "A", "lat": 25.0, "lng": 55.0, "female_pop_served": 1000,
            "communities_served": 1, "mean_distance_km": 1.0, "max_distance_km": 1.0,
            "contested_pop": 100, "contested_share": 0.1, "nearest_sibling_km": 5.0,
            "siblings_within_5km": 0, "avg_price_aed": 100.0, "price_index": 1.0, "rating": 4.5,
            "review_count": 10, "pop_per_1k_rank": 1, "estimated_fields": [],
        }],
    }))

    settings = Settings(_env_file=None, processed_dir=processed_dir, model_backend="rubric")
    main(settings)

    decisions = json.loads((processed_dir / "decisions.json").read_text())
    assert len(decisions) == 1
    assert decisions[0]["branch_id"] == "a"
