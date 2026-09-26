import json

import pytest
from httpx import ASGITransport, AsyncClient

from src.config import Settings
from src.serve.app import create_app


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


@pytest.fixture
def client(tmp_path):
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    _seed_processed(processed_dir)
    settings = Settings(_env_file=None, processed_dir=processed_dir, model_backend="rubric")
    app = create_app(settings)
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_health(client):
    async with client as c:
        resp = await c.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_branches_joined_with_decisions(client):
    async with client as c:
        resp = await c.get("/api/branches")
    body = resp.json()
    assert body[0]["branch_id"] == "a"
    assert body[0]["action"] == "PROTECT"


async def test_communities_joined_with_centroid(client):
    async with client as c:
        resp = await c.get("/api/communities")
    body = resp.json()
    assert body[0]["community_id"] == "c1"
    assert body[0]["lat"] == 25.05
    assert body[0]["name_en"] == "C1"


async def test_network(client):
    async with client as c:
        resp = await c.get("/api/network")
    body = resp.json()
    assert body["stats"]["branch_count"] == 1
    assert body["model_backend"] == "rubric"


async def test_network_reports_actual_backend_from_run_meta_not_configured_setting(tmp_path):
    # Fix 1: MODEL_BACKEND=llm is configured, but no API key was set at pipeline-run time,
    # so resolve_backend actually ran RubricModel and wrote run_meta.json={"model_backend":
    # "rubric"}. /api/network must report "rubric" (what actually ran), not "llm" (the
    # configured setting) -- otherwise the map header lies about data provenance.
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    _seed_processed(processed_dir)
    (processed_dir / "run_meta.json").write_text(json.dumps({"model_backend": "rubric"}))

    settings = Settings(_env_file=None, processed_dir=processed_dir, model_backend="llm",
                         anthropic_api_key=None)
    app = create_app(settings)
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")

    async with client as c:
        resp = await c.get("/api/network")
    body = resp.json()
    assert body["model_backend"] == "rubric"


async def test_network_falls_back_to_configured_backend_when_run_meta_absent(tmp_path):
    # If the pipeline hasn't run yet (no run_meta.json), fall back to the configured setting.
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    _seed_processed(processed_dir)
    assert not (processed_dir / "run_meta.json").exists()

    settings = Settings(_env_file=None, processed_dir=processed_dir, model_backend="rubric")
    app = create_app(settings)
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")

    async with client as c:
        resp = await c.get("/api/network")
    body = resp.json()
    assert body["model_backend"] == "rubric"


async def test_index_serves_html(client):
    async with client as c:
        resp = await c.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
