import json

from src.config import Settings
from src.model.run import main, resolve_backend
from src.model.llm import LLMModel
from src.model.rubric import RubricModel


def test_resolve_backend_falls_back_without_api_key():
    settings = Settings(_env_file=None, model_backend="llm", anthropic_api_key=None)
    model = resolve_backend(settings)
    assert isinstance(model, RubricModel)


def test_resolve_backend_honors_explicit_rubric():
    settings = Settings(_env_file=None, model_backend="rubric")
    model = resolve_backend(settings)
    assert isinstance(model, RubricModel)


def test_resolve_backend_returns_llm_model_when_backend_llm_and_key_set():
    # Only the two fallback-to-rubric paths were previously tested. This confirms the
    # actual "happy path" -- MODEL_BACKEND=llm with an API key present -- returns a real
    # LLMModel instance rather than silently falling back. No real API call is made; the
    # Anthropic client constructor doesn't touch the network.
    settings = Settings(_env_file=None, model_backend="llm", anthropic_api_key="fake-test-key")
    model = resolve_backend(settings)
    assert isinstance(model, LLMModel)
    assert model.name == "llm"


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

    run_meta = json.loads((processed_dir / "run_meta.json").read_text())
    assert run_meta["model_backend"] == "rubric"


def test_main_writes_run_meta_with_actual_backend_when_llm_falls_back_to_rubric(tmp_path):
    # Reproduces the Fix 1 scenario: MODEL_BACKEND=llm configured but no API key set, so
    # resolve_backend silently falls back to RubricModel. run_meta.json must record the
    # backend that actually ran ("rubric"), not the configured one ("llm").
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

    settings = Settings(_env_file=None, processed_dir=processed_dir, model_backend="llm",
                         anthropic_api_key=None)
    main(settings)

    run_meta = json.loads((processed_dir / "run_meta.json").read_text())
    assert run_meta["model_backend"] == "rubric"
