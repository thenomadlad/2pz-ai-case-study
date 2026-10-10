import json
from types import SimpleNamespace

from src import explain
from src.models import Explanation
from src.models import Evidence, Reason

# A HOLD lounge. Weighted distance of each score from neutral (0.5): capture 0.5, demand 0.22,
# rating 0.2 (half weight), cannibalisation 0.17 -> all four are arguments, in that order.
FACTS = {"catchment_women": 42648, "addressable_women": 56864, "affluence_rent": 75000.0,
         "affluence_coverage": 1.0, "catchment_cells": 3, "shared_share": 0.334,
         "premium_pool": 69, "substitutes_k": 12, "capture": 0.0, "thin_premium_market": False,
         "est_customers": 0, "lounge_rating": 4.7,
         "lounge_reviews": 396, "substitutes_median_rating": 4.8, "rating_gap": -0.1,
         "composite": 0.41, "score_demand": 0.2843, "score_cannibalisation": 0.666,
         "score_capture": 0.0, "score_rating": 0.1}
TOPICS = ["capture", "demand", "rating", "cannibalisation"]
EVIDENCE = {
    "capture": [("capture", 0.0), ("premium_pool", 69)],
    "demand": [("addressable_women", 56864), ("catchment_women", 42648)],
    "rating": [("lounge_rating", 4.7), ("lounge_reviews", 396)],
    "cannibalisation": [("shared_share", 0.334), ("score_cannibalisation", 0.666)],
}
CLAIMS = {"capture": "Capture is 0% against 69 premium salons.",
          "demand": "About 42,600 women live within a 15-min drive.",
          "rating": "Rated 4.7 from 396 reviews.",
          "cannibalisation": "33% of the catchment is shared."}
SO_WHAT = "About 42,600 women live in reach, and 33% of them are shared with a sibling."
NOW_WHAT = "No portfolio action this cycle; revisit at the next lease event."


def _exp(topics=TOPICS, claims=None, evidence=None, headline="HOLD: composite 0.41.",
         so_what=SO_WHAT, now_what=NOW_WHAT):
    claims, evidence = claims or CLAIMS, evidence or EVIDENCE
    return Explanation(
        subject_id="b", kind="lounge", action="HOLD", headline=headline, so_what=so_what,
        now_what=now_what,
        reasons=[Reason(topic=t, claim=claims[t],
                        evidence=[Evidence(field=f, label=f, value=v) for f, v in evidence[t]])
                 for t in topics],
        table_caption="Scores run 0 to 1.", thresholds_note="", source="ai")


def _lounge_facts(**scores):
    return {**FACTS, **{f"score_{k}": v for k, v in scores.items()}}


# --- prioritization ---------------------------------------------------------------------

def test_prioritize_hold_ranks_every_signal_far_from_neutral():
    assert explain.prioritize("lounge", FACTS, "HOLD") == TOPICS


def test_prioritize_shrink_keeps_only_weaknesses():
    facts = _lounge_facts(demand=0.23, cannibalisation=0.13, capture=0.30, rating=0.6)
    assert explain.prioritize("lounge", facts, "SHRINK") == [
        "cannibalisation", "demand", "capture"]  # rating supports the lounge: left out


def test_prioritize_always_gives_at_least_two_arguments():
    facts = _lounge_facts(demand=1.0, cannibalisation=0.55, capture=0.5, rating=0.45)
    topics = explain.prioritize("lounge", facts, "PROTECT")
    assert topics[0] == "demand" and len(topics) == 2


def test_prioritize_area_cases():
    base = {"women": 60_000, "skip_under_women": 10_000, "unsaturated": True,
            "worker_share": 0.1, "worker_cap": 0.5, "data_coverage": 0.9, "min_coverage": 0.5}
    assert explain.prioritize("area", base, "GROW") == ["size", "saturation", "reach"]
    assert explain.prioritize("area", {**base, "unsaturated": None}, "WATCH") == [
        "size", "data_gap", "reach"]
    assert explain.prioritize("area", {**base, "worker_share": 0.6}, "WATCH")[-1] == "worker_housing"
    assert explain.prioritize("area", {**base, "data_coverage": 0.2}, "WATCH")[-1] == "data_gap"
    assert explain.prioritize("area", {**base, "women": 5_000}, "SKIP") == ["size", "reach"]


def test_prioritize_uae_skips_empty_groups():
    facts = {"shrink_count": 0, "grow_count": 4, "protect_count": 2}
    assert explain.prioritize("uae", facts, "SUMMARY") == [
        "grow", "protect", "confidence", "data_gaps"]


# --- grounding check ----------------------------------------------------------------------

def test_verify_accepts_grounded_explanation():
    assert explain.verify(_exp(), FACTS, "lounge") == []


def test_verify_rejects_wrong_order_or_missing_argument():
    assert any("in that order" in e for e in explain.verify(_exp(topics=TOPICS[::-1]), FACTS,
                                                            "lounge"))
    assert any("in that order" in e for e in explain.verify(_exp(topics=TOPICS[:2]), FACTS,
                                                            "lounge"))


def test_verify_bounds_data_points_and_requires_own_topic():
    one = {**EVIDENCE, "demand": [("addressable_women", 56864)]}
    assert any("1 data points" in e for e in explain.verify(_exp(evidence=one), FACTS, "lounge"))
    six = {**EVIDENCE, "demand": EVIDENCE["demand"] * 3}
    assert any("6 data points" in e for e in explain.verify(_exp(evidence=six), FACTS, "lounge"))
    off_topic = {**EVIDENCE, "demand": EVIDENCE["rating"]}
    assert any("must cite at least one" in e
               for e in explain.verify(_exp(evidence=off_topic), FACTS, "lounge"))


def test_verify_rejects_wrong_value_unknown_field_and_invented_number():
    bad = {**EVIDENCE, "rating": [("lounge_rating", 4.9), ("lounge_reviews", 396)]}
    assert any("lounge_rating" in e for e in explain.verify(_exp(evidence=bad), FACTS, "lounge"))
    unknown = {**EVIDENCE, "rating": [("revenue", 1), ("lounge_rating", 4.7)]}
    assert any("unknown field" in e
               for e in explain.verify(_exp(evidence=unknown), FACTS, "lounge"))
    invented = {**CLAIMS, "demand": "Revenue fell 23% last year."}
    assert any("23" in e for e in explain.verify(_exp(claims=invented), FACTS, "lounge"))
    assert any("99" in e for e in explain.verify(_exp(headline="HOLD at 99."), FACTS, "lounge"))


def test_verify_accepts_numbers_rounded_to_the_precision_written():
    facts = {**FACTS, "substitutes_median_rating": 4.36}
    ev = {**EVIDENCE, "rating": [("lounge_rating", 4.7), ("substitutes_median_rating", 4.36)]}
    ok = {**CLAIMS, "rating": "Rated 4.7 against a 4.4 substitute median."}
    assert explain.verify(_exp(claims=ok, evidence=ev), facts, "lounge") == []
    hundreds = {**ok, "demand": "About 42,600 women; roughly 43,000."}
    assert explain.verify(_exp(claims=hundreds, evidence=ev), facts, "lounge") == []
    wrong = {**ok, "rating": "Rated 4.7 against a 4.5 substitute median."}
    assert any("4.5" in e for e in explain.verify(_exp(claims=wrong, evidence=ev), facts,
                                                  "lounge"))
    off = {**ok, "demand": "About 42,500 women."}  # 42,648 rounds to 42,600, not 42,500
    assert any("42500" in e for e in explain.verify(_exp(claims=off, evidence=ev), facts,
                                                    "lounge"))


def test_verify_requires_so_what_and_now_what():
    assert any("so_what" in e for e in explain.verify(_exp(so_what=""), FACTS, "lounge"))
    assert any("now_what" in e for e in explain.verify(_exp(now_what=" "), FACTS, "lounge"))


def test_verify_checks_numbers_in_so_what_and_now_what():
    errors = explain.verify(_exp(now_what="No portfolio action; 77 women would flip it."), FACTS,
                            "lounge")
    assert any("77" in e for e in errors)


def test_verify_rejects_a_mismatched_label():
    assert any("headline must name the call HOLD" in e
               for e in explain.verify(_exp(headline="SHRINK: composite 0.41."), FACTS, "lounge"))
    # Another label may follow the call ("0.06 above the SHRINK line"), never lead it.
    assert explain.verify(_exp(headline="HOLD: composite 0.41, above the SHRINK line."), FACTS,
                          "lounge") == []
    assert any("now_what must give the HOLD action" in e
               for e in explain.verify(_exp(now_what="Investigate a downsize."), FACTS, "lounge"))


def test_verify_rejects_in_branch_advice():
    advice = "No portfolio action. Improving its rating is the lever to watch."
    assert any("in-branch" in e for e in explain.verify(_exp(now_what=advice), FACTS, "lounge"))


def test_verify_ignores_digits_inside_ids():
    facts = {"nearest_lounge_id": "mirdif-35", "nearest_lounge_km": 2.0, "women": 1,
             "skip_under_women": 10}
    exp = Explanation(subject_id="a", kind="area", action="SKIP", headline="",
                      reasons=[], table_caption="Nearest is Mirdif-35.", thresholds_note="",
                      source="ai")
    assert not [e for e in explain.verify(exp, facts, "area") if "number in" in e]


# --- templates ------------------------------------------------------------------------

def test_lounge_template_is_grounded():
    assert explain.verify(explain.template_explanation("lounge", "b", "HOLD", FACTS), FACTS,
                          "lounge") == []


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
            "so_what": SO_WHAT, "now_what": NOW_WHAT,
            "reasons": [{"topic": t, "claim": claims[t],
                         "evidence": [{"field": f, "value": v} for f, v in EVIDENCE[t]]}
                        for t in TOPICS]}


def test_explain_retries_then_falls_back_to_template():
    exp = explain.explain("lounge", "b", "HOLD", FACTS, cache={},
                          client=_client([_payload("Made up 99 thing")] * 2))
    assert exp.source == "template"


def test_explain_uses_ai_when_grounded_and_caches_it():
    cache = {}
    exp = explain.explain("lounge", "b", "HOLD", FACTS, cache=cache,
                          client=_client([_payload("Made up 99"), _payload()]))
    assert exp.source == "ai" and exp.headline == "HOLD: composite 0.41."
    assert [r.topic for r in exp.reasons] == TOPICS
    assert len(cache) == 1
    # Cache hit: no client needed the second time.
    assert explain.explain("lounge", "b", "HOLD", FACTS, cache=cache).source == "ai"


def test_explain_through_the_real_sdk_with_a_mocked_transport():
    """K2: the paid path end to end through anthropic.Anthropic, with no network."""
    import anthropic
    import httpx2 as httpx  # the SDK's own HTTP client package

    sent = []

    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": "m",
            "stop_reason": "tool_use", "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1},
            "content": [{"type": "tool_use", "id": "t1", "name": "submit_explanation",
                         "input": _payload()}]})

    client = anthropic.Anthropic(api_key="test", max_retries=0,
                                 http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    exp = explain.explain("lounge", "b", "HOLD", FACTS, cache={}, client=client)
    assert exp.source == "ai" and exp.now_what == NOW_WHAT and len(sent) == 1
    assert sent[0]["tools"][0]["name"] == "submit_explanation"


def test_explain_falls_back_to_template_on_refusal():
    exp = explain.explain("lounge", "b", "HOLD", FACTS, cache={},
                          client=_client([_payload()], stop_reason="refusal"))
    assert exp.source == "template"


def test_cache_key_changes_when_numbers_change():
    k1 = explain.cache_key("lounge", "b", "HOLD", FACTS)
    k2 = explain.cache_key("lounge", "b", "HOLD", {**FACTS, "lounge_rating": 4.6})
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
    fields = set(explain.LOUNGE_TABLE) | set(explain.AREA_TABLE)
    fields |= {f for topics in explain.TOPICS.values() for fs in topics.values() for f in fs}
    for field in fields:
        assert explain.GLOSSARY[field].label and explain.GLOSSARY[field].meaning
    assert set(explain.TOPIC_LABELS) >= {t for ts in explain.TOPICS.values() for t in ts}


# --- v3 kinds ---------------------------------------------------------------------------

def test_v3_templates_are_grounded_for_every_subject():
    from src.explain import GLOSSARY, TOPICS, template_explanation, v3_subjects, verify
    subjects = v3_subjects()
    assert {k for k, *_ in subjects} == {"uae", "lounge", "area"}
    for kind, sid, action, facts in subjects:
        assert verify(template_explanation(kind, sid, action, facts), facts, kind) == [], sid
        assert all(k in GLOSSARY for k in facts), sid
        table = {"lounge": explain.LOUNGE_TABLE, "area": explain.AREA_TABLE}.get(kind, ())
        assert action == "NOT SCORED" or set(table) <= set(facts), sid
    assert all(f in GLOSSARY for t in ("lounge", "area", "uae") for fs in TOPICS[t].values()
               for f in fs)


def test_not_scored_lounge_never_goes_to_the_llm():
    from src.explain import explain, v3_subjects
    kind, sid, action, facts = next(s for s in v3_subjects() if s[2] == "NOT SCORED")

    class Boom:
        class beta:
            class messages:
                @staticmethod
                def create(**_):
                    raise AssertionError("LLM called for a NOT SCORED lounge")

    exp = explain(kind, sid, action, facts, cache={}, client=Boom())
    assert exp.source == "template" and exp.headline.startswith("Not scored")


def test_lounge_contributions_sum_and_flip_value_reaches_the_line():
    from src.model import scorecard
    for kind, sid, action, f in explain.v3_subjects():
        if kind != "lounge" or action == "NOT SCORED":
            continue
        contribs = sum(f[f"contrib_{s.name}"] for s in scorecard.SIGNALS)
        assert abs(contribs - f["composite"]) < 1e-3, sid
        assert f["line_gap"] >= 0 and f["next_call"] != action, sid
        if f["flip_driver"]:
            sig = next(s for s in scorecard.SIGNALS if s.name == f["flip_driver"])
            moved = f["composite"] + sig.weight * (scorecard.score(sig, f["flip_value"])
                                                   - f[f"score_{sig.name}"]) / 3.5
            line = {"PROTECT": scorecard.PROTECT_AT, "SHRINK": scorecard.SHRINK_AT}.get(
                action, {"PROTECT": scorecard.PROTECT_AT}.get(f["next_call"], scorecard.SHRINK_AT))
            assert abs(moved - line) < 1e-3, sid


def test_area_gaps_agree_with_the_tests():
    for kind, sid, _action, f in explain.v3_subjects():
        if kind != "area":
            continue
        assert (f["size_gap"] >= 0 and f["worker_gap"] > 0) == f["big_enough"], sid
        if f["unsaturated"] is not None:
            assert (f["saturation_gap"] > 0) == f["unsaturated"], sid


def test_every_committed_cache_entry_is_current_and_grounded():
    """D3/E5: the committed cache holds exactly today's AI subjects, and each passes verify()."""
    cache = explain.load_cache()
    subjects = [s for s in explain.v3_subjects() if explain.needs_ai(s[2])]
    keys = {explain.cache_key(*s): s for s in subjects}
    assert set(cache) == set(keys)
    for key, (kind, sid, _action, facts) in keys.items():
        assert explain.verify(Explanation(**cache[key]), facts, kind) == [], sid
