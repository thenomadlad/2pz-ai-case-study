import json
from unittest.mock import MagicMock

from src.model.llm import LLMModel, _cache_key
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


def test_decide_overrides_hallucinated_branch_id_with_actual_branch_id(tmp_path):
    # If the LLM echoes back a typo'd/hallucinated branch_id, we must not trust it -- it's
    # the join key used downstream by /api/branches. The Decision's branch_id must always
    # match the branch we actually passed in.
    branch = _features()
    decision_payload = {
        "branch_id": "totally-wrong-id", "action": "PROTECT", "confidence": "high",
        "rationale": "Strong population, low contest.",
        "key_drivers": ["female_pop_served", "contested_share"], "caveats": ["No revenue data."],
    }
    client = MagicMock()
    client.messages.create.return_value = _tool_use_response(decision_payload)

    model = LLMModel(client=client, model_name="test-model", cache_dir=tmp_path)
    decisions = model.decide([branch], NETWORK)

    assert decisions[0].branch_id == "a"


def test_decide_falls_back_to_rubric_when_api_call_raises(tmp_path):
    # If the Anthropic API call fails (rate limit, network error, expired key), the pipeline
    # must not crash with a raw traceback -- it should fall back to a rubric decision for
    # that branch, matching the "log loudly, fall back gracefully" philosophy used elsewhere.
    branch = _features()
    client = MagicMock()
    client.messages.create.side_effect = RuntimeError("simulated API failure")

    model = LLMModel(client=client, model_name="test-model", cache_dir=tmp_path)
    decisions = model.decide([branch], NETWORK)

    assert len(decisions) == 1
    assert decisions[0].branch_id == "a"
    assert decisions[0].action in ("PROTECT", "HOLD", "SHRINK")


def test_decide_falls_back_to_rubric_when_no_tool_use_block_returned(tmp_path):
    # If the model responds without a tool-use block (e.g. hits max_tokens mid-call or
    # refuses), the bare `next(...)` StopIteration must not propagate -- fall back to rubric.
    branch = _features()
    text_block = MagicMock()
    text_block.type = "text"
    response = MagicMock()
    response.content = [text_block]
    client = MagicMock()
    client.messages.create.return_value = response

    model = LLMModel(client=client, model_name="test-model", cache_dir=tmp_path)
    decisions = model.decide([branch], NETWORK)

    assert len(decisions) == 1
    assert decisions[0].branch_id == "a"


def test_cache_key_changes_with_feature_vector():
    branch = _features()
    other = branch.model_copy(update={"female_pop_served": 9999})
    key1 = _cache_key(branch, "test-model")
    key2 = _cache_key(other, "test-model")
    assert key1 != key2


def _create_side_effect_for(branch_id_to_fail, success_payload_by_id):
    def create_side_effect(*args, **kwargs):
        user_content = json.loads(kwargs["messages"][0]["content"])
        branch_id = user_content["branch"]["branch_id"]
        if branch_id == branch_id_to_fail:
            raise RuntimeError("simulated API failure")
        return _tool_use_response(success_payload_by_id[branch_id])
    return create_side_effect


def test_decide_marks_fallback_decision_low_confidence_with_caveat_others_unaffected(tmp_path):
    # Regression test for defect 2 (mislabeled provenance): a branch whose API call fails must
    # come back with confidence == "low" and a caveat explaining the LLM call failed, while a
    # sibling branch in the same batch whose API call succeeds must be completely unaffected.
    branch_ok = _features()
    branch_fail = branch_ok.model_copy(update={"branch_id": "b"})

    success_payload = {
        "branch_id": "a", "action": "PROTECT", "confidence": "high",
        "rationale": "Strong population, low contest.",
        "key_drivers": ["female_pop_served"], "caveats": ["No revenue data."],
    }
    client = MagicMock()
    client.messages.create.side_effect = _create_side_effect_for("b", {"a": success_payload})

    model = LLMModel(client=client, model_name="test-model", cache_dir=tmp_path)
    decisions = model.decide([branch_ok, branch_fail], NETWORK)
    by_id = {d.branch_id: d for d in decisions}

    assert by_id["a"].confidence == "high"
    assert by_id["a"].caveats == ["No revenue data."]

    assert by_id["b"].confidence == "low"
    assert any("LLM call failed" in c for c in by_id["b"].caveats)


def test_decide_does_not_cache_fallback_and_retries_api_on_next_call(tmp_path):
    # Regression test for defect 1 (cache poisoning). Confirmed by execution before the fix:
    # a failing call would write the fallback decision to the cache dir, and a second call with
    # a now-healthy client would return the stale cached fallback with call_count == 0 (the API
    # was never retried). After the fix, nothing should be cached on the failure path, and a
    # second call must actually invoke the (now healthy) client.
    branch = _features()
    failing_client = MagicMock()
    failing_client.messages.create.side_effect = RuntimeError("simulated API failure")

    model = LLMModel(client=failing_client, model_name="test-model", cache_dir=tmp_path)
    model.decide([branch], NETWORK)

    assert list(tmp_path.glob("*.json")) == []

    healthy_client = MagicMock()
    recovered_payload = {
        "branch_id": "a", "action": "HOLD", "confidence": "medium",
        "rationale": "Recovered.", "key_drivers": ["rating"], "caveats": [],
    }
    healthy_client.messages.create.return_value = _tool_use_response(recovered_payload)
    model2 = LLMModel(client=healthy_client, model_name="test-model", cache_dir=tmp_path)
    decisions = model2.decide([branch], NETWORK)

    healthy_client.messages.create.assert_called_once()
    assert decisions[0].action == "HOLD"
    assert decisions[0].confidence == "medium"


def test_decide_fallback_bucketing_uses_full_batch_not_lone_branch_index_zero(tmp_path):
    # Regression test for defect 2 (always-PROTECT bucketing bug). RubricModel's top_third =
    # max(1, n // 3) means a single-branch batch always lands that branch in the PROTECT tier
    # regardless of its features. Construct a 3-branch batch where the failing branch has by
    # far the worst features -- it should rank SHRINK against its peers, not PROTECT.
    branch_best = _features()  # branch_id "a": strong pop/contest/rating
    branch_fail = branch_best.model_copy(update={
        "branch_id": "b", "female_pop_served": 200, "contested_share": 0.9, "rating": 2.0,
    })
    branch_mid = branch_best.model_copy(update={
        "branch_id": "c", "female_pop_served": 1000, "contested_share": 0.5, "rating": 3.0,
    })

    success_payload_by_id = {
        "a": {"branch_id": "a", "action": "PROTECT", "confidence": "high", "rationale": "ok",
              "key_drivers": ["female_pop_served"], "caveats": []},
        "c": {"branch_id": "c", "action": "HOLD", "confidence": "medium", "rationale": "ok",
              "key_drivers": ["rating"], "caveats": []},
    }
    client = MagicMock()
    client.messages.create.side_effect = _create_side_effect_for("b", success_payload_by_id)

    model = LLMModel(client=client, model_name="test-model", cache_dir=tmp_path)
    decisions = model.decide([branch_best, branch_fail, branch_mid], NETWORK)
    by_id = {d.branch_id: d for d in decisions}

    assert by_id["b"].action == "SHRINK"
    assert by_id["b"].confidence == "low"
    assert any("LLM call failed" in c for c in by_id["b"].caveats)
