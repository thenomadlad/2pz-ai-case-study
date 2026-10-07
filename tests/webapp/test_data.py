import json

from src.config import Settings
from src.model.run import PIPELINE_VERSION
from src.webapp.data import load_baseline


def _seed_processed(processed_dir):
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
    (processed_dir / "community_assignment.json").write_text(json.dumps([{
        "community_id": "c1", "nearest_branch_id": "a", "nearest_km": 1.0,
        "second_branch_id": None, "second_km": None, "contested": False, "female_pop": 500,
    }]))
    (processed_dir / "communities.json").write_text(json.dumps([{
        "id": "c1", "name_en": "C1", "lat": 25.05, "lng": 55.15,
        "population_total": 1000, "population_female": 500, "is_estimated": False,
    }]))
    (processed_dir / "decisions.json").write_text(json.dumps([{
        "branch_id": "a", "action": "PROTECT", "confidence": "high",
        "rationale": "Strong branch.", "key_drivers": ["female_pop_served"], "caveats": [],
    }]))
    (processed_dir / "community_features.json").write_text(json.dumps([{
        "community_id": "c1", "name": "C1", "lat": 25.05, "lng": 55.15, "female_pop": 500,
        "competitors": 0, "competitors_per_10k": 0.0, "nearest_branch_id": "a",
        "nearest_branch_km": 1.0, "nearest_branch_pop_served": 1000, "hosts_branch": True,
    }]))
    (processed_dir / "opportunities.json").write_text(json.dumps([{
        "community_id": "c1", "action": "SKIP", "underserved": False, "unsaturated": True,
        "rationale": "Already hosts a Bedashing branch.", "caveats": [],
    }]))
    (processed_dir / "run_meta.json").write_text(json.dumps(
        {"model": "rubric", "pipeline_version": PIPELINE_VERSION}))


def test_load_baseline_joins_decisions_and_opportunities(tmp_path):
    processed_dir = tmp_path / "processed" / "baseline"
    processed_dir.mkdir(parents=True)
    _seed_processed(processed_dir)

    data = load_baseline(Settings(_env_file=None, processed_dir=processed_dir,
                                  raw_dir=tmp_path / "raw"))

    assert data.network.branch_count == 1
    assert data.decision_for("a").action == "PROTECT"
    assert data.decision_for("missing") is None
    assert data.opportunity_for("c1").action == "SKIP"
    assert data.communities_by_id()["c1"].name_en == "C1"
    assert data.competitors == []  # no raw competitors.json under tmp_path


def test_load_baseline_regenerates_an_older_pipeline_version(tmp_path, monkeypatch):
    processed_dir = tmp_path / "processed" / "baseline"
    processed_dir.mkdir(parents=True)
    _seed_processed(processed_dir)
    (processed_dir / "run_meta.json").write_text(json.dumps({"model_backend": "llm"}))
    calls = []
    monkeypatch.setattr("src.scenario.baseline.main", lambda s: calls.append(s))

    load_baseline(Settings(_env_file=None, processed_dir=processed_dir,
                           raw_dir=tmp_path / "raw"))

    assert len(calls) == 1
