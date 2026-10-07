from types import SimpleNamespace

from src import explain
from src.models import BranchFeatures, Decision, Evidence, Explanation, Reason

FACTS = {"female_pop_served": 42648, "contested_share": 0.334, "rating": 4.7,
         "communities_served": 3, "nearest_sibling_km": 2.1, "competitors_per_10k": 16.2,
         "competitors_in_catchment": 69, "review_count": 396, "composite": 0.41,
         "score_demand": 0.2843, "score_cannibalisation": 0.666, "score_competition": 0.0,
         "score_quality": 0.7}


def _exp(claims, evidence, caption="Scores run 0 to 1."):
    return Explanation(subject_id="b", kind="branch", action="HOLD",
                       reasons=[Reason(claim=c, evidence=[Evidence(field=f, label=f, value=v)
                                                          for f, v in evidence])
                                for c in claims],
                       table_caption=caption, thresholds_note="", source="ai")


GOOD_EVIDENCE = [("competitors_per_10k", 16.2), ("competitors_in_catchment", 69)]


def test_verify_accepts_grounded_explanation():
    exp = _exp(["16.2 rival salons per 10k women, 69 in total.",
                "Cannibalisation is 33% of the catchment.",
                "Rated 4.7 from 396 reviews."], GOOD_EVIDENCE)
    assert explain.verify(exp, FACTS, "branch") == []


def test_verify_rejects_wrong_value_unknown_field_and_invented_number():
    bad_value = _exp(["a", "b", "c"], [("rating", 4.9), ("review_count", 396)])
    assert any("rating" in e for e in explain.verify(bad_value, FACTS, "branch"))
    unknown = _exp(["a", "b", "c"], [("revenue", 1), ("rating", 4.7)])
    assert any("unknown field" in e for e in explain.verify(unknown, FACTS, "branch"))
    invented = _exp(["Revenue fell 23% last year.", "b", "c"], GOOD_EVIDENCE)
    assert any("23" in e for e in explain.verify(invented, FACTS, "branch"))


def test_template_is_always_grounded():
    exp = explain.template_explanation("branch", "b", "HOLD", FACTS)
    assert exp.source == "template"
    assert explain.verify(exp, FACTS, "branch") == []


def _client(payloads, stop_reason="tool_use"):
    calls = iter(payloads)

    def create(**kwargs):
        assert "temperature" not in kwargs and "tool_choice" not in kwargs  # 400 on Opus 5.5
        return SimpleNamespace(stop_reason=stop_reason, stop_details=None,
                               content=[SimpleNamespace(type="tool_use", input=next(calls))])
    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))


def _payload(claim):
    ev = [{"field": "rating", "value": 4.7}, {"field": "review_count", "value": 396}]
    return {"reasons": [{"claim": claim, "evidence": ev}] * 3,
            "table_caption": "Each factor is scored 0 to 1."}


def test_explain_retries_then_falls_back_to_template():
    exp = explain.explain("branch", "b", "HOLD", FACTS, cache={},
                          client=_client([_payload("Made up 99 thing")] * 2))
    assert exp.source == "template"


def test_explain_uses_ai_when_grounded_and_caches_it():
    cache = {}
    exp = explain.explain("branch", "b", "HOLD", FACTS, cache=cache,
                          client=_client([_payload("Made up 99"), _payload("Rated 4.7.")]))
    assert exp.source == "ai"
    assert len(cache) == 1
    # Cache hit: no client needed the second time.
    assert explain.explain("branch", "b", "HOLD", FACTS, cache=cache).source == "ai"


def test_cache_key_changes_when_numbers_change():
    k1 = explain.cache_key("branch", "b", "HOLD", FACTS)
    k2 = explain.cache_key("branch", "b", "HOLD", {**FACTS, "rating": 4.6})
    assert k1 != k2


def test_every_table_field_has_glossary_unit_and_meaning():
    for field in explain.BRANCH_TABLE + explain.OPPORTUNITY_TABLE:
        g = explain.GLOSSARY[field]
        assert g.label and g.meaning


def test_branch_facts_cover_branch_table():
    f = BranchFeatures(branch_id="b", name="B", lat=25, lng=55, female_pop_served=1,
                       communities_served=1, mean_distance_km=1, max_distance_km=1,
                       contested_pop=0, contested_share=0, nearest_sibling_km=1,
                       siblings_within_5km=0, avg_price_aed=99, price_index=1, rating=4.5,
                       review_count=1, pop_per_1k_rank=1, estimated_fields=[])
    d = Decision(branch_id="b", action="HOLD", confidence="low", rationale="", key_drivers=[],
                 caveats=[], composite=0.5,
                 scores={"demand": 0.5, "cannibalisation": 0.5, "competition": 0.5,
                         "quality": 0.5})
    assert set(explain.BRANCH_TABLE) <= set(explain.branch_facts(f, d))


def test_explain_falls_back_to_template_on_refusal():
    exp = explain.explain("branch", "b", "HOLD", FACTS, cache={},
                          client=_client([_payload("Rated 4.7.")], stop_reason="refusal"))
    assert exp.source == "template"


def test_tool_schema_is_strict_compatible():
    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node.get("additionalProperties") is False
            assert "minItems" not in node and "maxItems" not in node
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    assert explain.EXPLAIN_TOOL["strict"] is True
    walk(explain.EXPLAIN_TOOL["input_schema"])


def test_verify_accepts_numbers_rounded_to_the_precision_written():
    facts = {**FACTS, "competitors_per_10k": 3.06, "nearest_sibling_km": 7.64}
    ok = _exp(["3.1 rival salons per 10k women.", "Nearest sibling 7.6 km away.",
               "Cannibalisation is 33%."], GOOD_EVIDENCE[:1] + [("rating", 4.7)])
    assert not [e for e in explain.verify(ok, facts, "branch") if "number" in e]
    wrong = _exp(["3.2 rival salons per 10k women.", "b", "c"], [("rating", 4.7),
                                                                ("review_count", 396)])
    assert any("3.2" in e for e in explain.verify(wrong, facts, "branch"))
