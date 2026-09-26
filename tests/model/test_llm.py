import json
from unittest.mock import MagicMock

from src.model.llm import LLMModel, PROMPT_VERSION, _cache_key
from src.models import BranchFeatures, NetworkStats


def _features():
    return BranchFeatures(
        branch_id="a", name="A", lat=25.0, lng=55.0, female_pop_served=2000,
        communities_served=1, mean_distance_km=1.0, max_distance_km=1.0, contested_pop=200,
        contested_share=0.1, nearest_sibling_km=5.0, siblings_within_5km=0, avg_price_aed=100.0,
        price_index=1.0, rating=4.5, review_count=50, pop_per_1k_rank=1, estimated_fields=[],
    )


NETWORK = NetworkStats(
    branch_count=1, total_female_population=2000,
    female_pop_served_median=2000, female_pop_served_p25=2000, female_pop_served_p75=2000,
    contested_share_median=0.1, contested_share_p25=0.1, contested_share_p75=0.1,
    avg_price_aed_median=100, avg_price_aed_p25=100, avg_price_aed_p75=100,
    rating_median=4.5, rating_p25=4.5, rating_p75=4.5,
)


def _tool_use_response(decision_dict):
    block = MagicMock()
    block.type = "tool_use"
    block.input = decision_dict
    response = MagicMock()
    response.content = [block]
    return response


def test_decide_calls_client_and_returns_decision(tmp_path):
    branch = _features()
    decision_payload = {
        "branch_id": "a", "action": "PROTECT", "confidence": "high",
        "rationale": "Strong population, low contest.",
        "key_drivers": ["female_pop_served", "contested_share"], "caveats": ["No revenue data."],
    }
    client = MagicMock()
    client.messages.create.return_value = _tool_use_response(decision_payload)

    model = LLMModel(client=client, model_name="test-model", cache_dir=tmp_path)
    decisions = model.decide([branch], NETWORK)

    assert decisions[0].action == "PROTECT"
    client.messages.create.assert_called_once()


def test_decide_uses_cache_on_second_call(tmp_path):
    branch = _features()
    decision_payload = {
        "branch_id": "a", "action": "HOLD", "confidence": "medium",
        "rationale": "Middling numbers.", "key_drivers": ["rating"], "caveats": [],
    }
    client = MagicMock()
    client.messages.create.return_value = _tool_use_response(decision_payload)

    model = LLMModel(client=client, model_name="test-model", cache_dir=tmp_path)
    model.decide([branch], NETWORK)
    model.decide([branch], NETWORK)

    assert client.messages.create.call_count == 1


def test_cache_key_changes_with_feature_vector():
    branch = _features()
    other = branch.model_copy(update={"female_pop_served": 9999})
    key1 = _cache_key(branch, "test-model")
    key2 = _cache_key(other, "test-model")
    assert key1 != key2
