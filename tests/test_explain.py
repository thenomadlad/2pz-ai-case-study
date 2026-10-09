from types import SimpleNamespace

from src import explain
from src.models import (
    BranchFeatures,
    CommunityFeatures,
    Decision,
    Evidence,
    Explanation,
    OpportunityDecision,
    Reason,
)

# A HOLD branch. Distance of each score from neutral (0.5): competition 0.5, demand 0.22,
# quality 0.2, cannibalisation 0.17 -> all four are arguments, in that order.
FACTS = {"female_pop_served": 42648, "contested_share": 0.334, "rating": 4.7,
         "communities_served": 3, "nearest_sibling_km": 2.1, "competitors_per_10k": 16.2,
         "competitors_in_catchment": 69, "review_count": 396, "composite": 0.41,
         "score_demand": 0.2843, "score_cannibalisation": 0.666, "score_competition": 0.0,
         "score_quality": 0.7}
TOPICS = ["competition", "demand", "quality", "cannibalisation"]
EVIDENCE = {
    "competition": [("competitors_per_10k", 16.2), ("competitors_in_catchment", 69)],
    "demand": [("female_pop_served", 42648), ("communities_served", 3)],
    "quality": [("rating", 4.7), ("review_count", 396)],
    "cannibalisation": [("contested_share", 0.334), ("nearest_sibling_km", 2.1)],
}
CLAIMS = {"competition": "16.2 rival salons per 10k women, 69 in total.",
          "demand": "About 42,600 women live nearest this branch.",
          "quality": "Rated 4.7 from 396 reviews.",
          "cannibalisation": "Cannibalisation is 33% of the catchment."}


def _exp(topics=TOPICS, claims=None, evidence=None, headline="HOLD: composite 0.41."):
    claims, evidence = claims or CLAIMS, evidence or EVIDENCE
    return Explanation(
        subject_id="b", kind="branch", action="HOLD", headline=headline,
        reasons=[Reason(topic=t, claim=claims[t],
                        evidence=[Evidence(field=f, label=f, value=v) for f, v in evidence[t]])
                 for t in topics],
        table_caption="Scores run 0 to 1.", thresholds_note="", source="ai")


def _branch_facts(**scores):
    return {**FACTS, **{f"score_{k}": v for k, v in scores.items()}}


# --- prioritization ---------------------------------------------------------------------

def test_prioritize_hold_ranks_every_signal_far_from_neutral():
    assert explain.prioritize("branch", FACTS, "HOLD") == TOPICS


def test_prioritize_shrink_keeps_only_weaknesses():
    facts = _branch_facts(demand=0.23, cannibalisation=0.13, competition=0.30, quality=0.6)
    assert explain.prioritize("branch", facts, "SHRINK") == [
        "cannibalisation", "demand", "competition"]  # quality supports the branch: left out


def test_prioritize_always_gives_at_least_two_arguments():
    facts = _branch_facts(demand=1.0, cannibalisation=0.55, competition=0.5, quality=0.45)
    topics = explain.prioritize("branch", facts, "PROTECT")
    assert topics[0] == "demand" and len(topics) == 2


def test_prioritize_opportunity_cases():
    base = {"hosts_branch": False, "female_pop": 30_000, "min_pop_floor": 20_000,
            "worker_housing": False, "underserved": True, "unsaturated": True}
    assert explain.prioritize("opportunity", base, "GROW") == [
        "coverage", "competition", "headroom", "demand"]
    assert explain.prioritize("opportunity", {**base, "hosts_branch": True}, "SKIP")[0] == "presence"
    assert explain.prioritize("opportunity", {**base, "female_pop": 5_000}, "SKIP")[0] == "demand"
    assert explain.prioritize("opportunity", {**base, "worker_housing": True},
                              "WATCH")[-1] == "worker_housing"


def test_prioritize_network_skips_empty_groups():
    facts = {"shrink_count": 0, "grow_count": 4, "protect_count": 2}
    assert explain.prioritize("network", facts, "SUMMARY") == [
        "grow", "protect", "confidence", "data_gaps"]


# --- grounding check ----------------------------------------------------------------------

def test_verify_accepts_grounded_explanation():
    assert explain.verify(_exp(), FACTS, "branch") == []


def test_verify_rejects_wrong_order_or_missing_argument():
    assert any("in that order" in e for e in explain.verify(_exp(topics=TOPICS[::-1]), FACTS,
                                                            "branch"))
    assert any("in that order" in e for e in explain.verify(_exp(topics=TOPICS[:2]), FACTS,
                                                            "branch"))


def test_verify_bounds_data_points_and_requires_own_topic():
    one = {**EVIDENCE, "demand": [("female_pop_served", 42648)]}
    assert any("1 data points" in e for e in explain.verify(_exp(evidence=one), FACTS, "branch"))
    six = {**EVIDENCE, "demand": EVIDENCE["demand"] * 3}
    assert any("6 data points" in e for e in explain.verify(_exp(evidence=six), FACTS, "branch"))
    off_topic = {**EVIDENCE, "demand": EVIDENCE["quality"]}
    assert any("must cite at least one" in e
               for e in explain.verify(_exp(evidence=off_topic), FACTS, "branch"))


def test_verify_rejects_wrong_value_unknown_field_and_invented_number():
    bad = {**EVIDENCE, "quality": [("rating", 4.9), ("review_count", 396)]}
    assert any("rating" in e for e in explain.verify(_exp(evidence=bad), FACTS, "branch"))
    unknown = {**EVIDENCE, "quality": [("revenue", 1), ("rating", 4.7)]}
    assert any("unknown field" in e
               for e in explain.verify(_exp(evidence=unknown), FACTS, "branch"))
    invented = {**CLAIMS, "demand": "Revenue fell 23% last year."}
    assert any("23" in e for e in explain.verify(_exp(claims=invented), FACTS, "branch"))
    assert any("99" in e for e in explain.verify(_exp(headline="HOLD at 99."), FACTS, "branch"))


def test_verify_accepts_numbers_rounded_to_the_precision_written():
    facts = {**FACTS, "competitors_per_10k": 3.06, "nearest_sibling_km": 7.64}
    ev = {**EVIDENCE, "competition": [("competitors_per_10k", 3.06),
                                      ("competitors_in_catchment", 69)],
          "cannibalisation": [("contested_share", 0.334), ("nearest_sibling_km", 7.64)]}
    ok = {**CLAIMS, "competition": "3.1 rival salons per 10k women.",
          "cannibalisation": "Nearest sibling 7.6 km away; 33% contested."}
    assert explain.verify(_exp(claims=ok, evidence=ev), facts, "branch") == []
    hundreds = {**ok, "demand": "About 42,600 women; roughly 43,000."}
    assert explain.verify(_exp(claims=hundreds, evidence=ev), facts, "branch") == []
    wrong = {**ok, "competition": "3.2 rival salons per 10k women."}
    assert any("3.2" in e for e in explain.verify(_exp(claims=wrong, evidence=ev), facts,
                                                  "branch"))
    off = {**ok, "demand": "About 42,500 women."}  # 42,648 rounds to 42,600, not 42,500
    assert any("42500" in e for e in explain.verify(_exp(claims=off, evidence=ev), facts,
                                                    "branch"))


def test_verify_ignores_digits_inside_ids():
    facts = {"nearest_branch_id": "mirdif-35", "nearest_branch_km": 2.0}
    exp = Explanation(subject_id="a", kind="opportunity", action="SKIP", headline="",
                      reasons=[], table_caption="Nearest is Mirdif-35.", thresholds_note="",
                      source="ai")
    assert not [e for e in explain.verify(exp, {**facts, "hosts_branch": True,
                                                "female_pop": 1, "min_pop_floor": 1},
                                          "opportunity") if "number" in e]


# --- templates ------------------------------------------------------------------------

def _community(**kw):
    base = {"community_id": "c", "name": "Al Rifa", "lat": 25.0, "lng": 55.0,
            "female_pop": 30_000, "competitors": 10, "competitors_per_10k": 3.3,
            "nearest_branch_id": "mirdif-35", "nearest_branch_km": 7.3,
            "nearest_branch_pop_served": 1, "hosts_branch": False}
    return CommunityFeatures(**{**base, **kw})


def test_templates_are_always_grounded():
    assert explain.verify(explain.template_explanation("branch", "b", "HOLD", FACTS), FACTS,
                          "branch") == []
    for c, action in [(_community(), "GROW"), (_community(hosts_branch=True), "SKIP"),
                      (_community(name="Jebel Ali Industrial First"), "WATCH")]:
        o = OpportunityDecision(community_id="c", action=action, underserved=True,
                                unsaturated=True, rationale="", caveats=[])
        facts = explain.opportunity_facts(c, o)
        exp = explain.template_explanation("opportunity", "c", action, facts)
        assert explain.verify(exp, facts, "opportunity") == []


def test_network_facts_and_template():
    decisions = [Decision(branch_id=b, action=a, confidence="low", rationale="",
                          key_drivers=[], caveats=[], composite=c)
                 for b, a, c in [("x", "PROTECT", 0.7), ("y", "SHRINK", 0.3), ("z", "HOLD", 0.5)]]
    opps = [OpportunityDecision(community_id="c", action="GROW", underserved=True,
                                unsaturated=True, rationale="", caveats=[])]
    facts = explain.network_facts(decisions, opps, [_community()], 768)
    assert facts["shrink_branches"] == "y" and facts["grow_areas"] == "c"
    exp = explain.template_explanation("network", "dubai", "SUMMARY", facts)
    assert [r.topic for r in exp.reasons] == ["shrink", "grow", "protect", "confidence",
                                              "data_gaps"]
    assert explain.verify(exp, facts, "network") == []


# --- LLM path -------------------------------------------------------------------------

def _client(payloads, stop_reason="tool_use"):
    calls = iter(payloads)

    def create(**kwargs):
        assert "temperature" not in kwargs and "tool_choice" not in kwargs  # 400 on Opus 5.5
        return SimpleNamespace(stop_reason=stop_reason, stop_details=None,
                               content=[SimpleNamespace(type="tool_use", input=next(calls))])
    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))


def _payload(demand_claim=CLAIMS["demand"]):
    claims = {**CLAIMS, "demand": demand_claim}
    return {"headline": "HOLD: composite 0.41.", "table_caption": "Scored 0 to 1.",
            "reasons": [{"topic": t, "claim": claims[t],
                         "evidence": [{"field": f, "value": v} for f, v in EVIDENCE[t]]}
                        for t in TOPICS]}


def test_explain_retries_then_falls_back_to_template():
    exp = explain.explain("branch", "b", "HOLD", FACTS, cache={},
                          client=_client([_payload("Made up 99 thing")] * 2))
    assert exp.source == "template"


def test_explain_uses_ai_when_grounded_and_caches_it():
    cache = {}
    exp = explain.explain("branch", "b", "HOLD", FACTS, cache=cache,
                          client=_client([_payload("Made up 99"), _payload()]))
    assert exp.source == "ai" and exp.headline == "HOLD: composite 0.41."
    assert [r.topic for r in exp.reasons] == TOPICS
    assert len(cache) == 1
    # Cache hit: no client needed the second time.
    assert explain.explain("branch", "b", "HOLD", FACTS, cache=cache).source == "ai"


def test_explain_falls_back_to_template_on_refusal():
    exp = explain.explain("branch", "b", "HOLD", FACTS, cache={},
                          client=_client([_payload()], stop_reason="refusal"))
    assert exp.source == "template"


def test_cache_key_changes_when_numbers_change():
    k1 = explain.cache_key("branch", "b", "HOLD", FACTS)
    k2 = explain.cache_key("branch", "b", "HOLD", {**FACTS, "rating": 4.6})
    assert k1 != k2


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


# --- glossary -----------------------------------------------------------------------

def test_every_fact_and_topic_field_has_a_glossary_entry():
    fields = set(explain.BRANCH_TABLE) | set(explain.OPPORTUNITY_TABLE)
    fields |= {f for topics in explain.TOPICS.values() for fs in topics.values() for f in fs}
    for field in fields:
        assert explain.GLOSSARY[field].label and explain.GLOSSARY[field].meaning
    assert set(explain.TOPIC_LABELS) >= {t for ts in explain.TOPICS.values() for t in ts}


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
