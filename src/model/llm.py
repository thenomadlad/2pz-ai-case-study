import hashlib
import json
import logging
from pathlib import Path

from src.config import settings as default_settings
from src.models import BranchFeatures, Decision, NetworkStats

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = (
    "You are a retail portfolio analyst for a UAE salon chain. You classify branches as "
    "PROTECT, HOLD or SHRINK. You only reason from the numbers provided. You never invent "
    "data. If the evidence is thin you say so in `caveats` and lower `confidence`."
)

DECISION_TOOL = {
    "name": "submit_decision",
    "description": "Submit the PROTECT/HOLD/SHRINK decision for this branch.",
    "input_schema": {
        "type": "object",
        "properties": {
            "branch_id": {"type": "string"},
            "action": {"type": "string", "enum": ["PROTECT", "HOLD", "SHRINK"]},
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            "rationale": {"type": "string"},
            "key_drivers": {"type": "array", "items": {"type": "string"}},
            "caveats": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["branch_id", "action", "confidence", "rationale", "key_drivers", "caveats"],
    },
}


def _cache_key(branch: BranchFeatures, model_name: str) -> str:
    payload = json.dumps({
        "prompt_version": PROMPT_VERSION,
        "model": model_name,
        "features": branch.model_dump(),
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _build_user_message(branch: BranchFeatures, network: NetworkStats) -> str:
    return json.dumps({
        "definitions": {
            "PROTECT": "Invest to defend this branch's position.",
            "HOLD": "Keep as-is, no strong signal either way.",
            "SHRINK": "Candidate for downsizing or closure.",
        },
        "network_context": network.model_dump(),
        "branch": branch.model_dump(),
        "unknown_to_you": [
            "revenue", "footfall", "staffing", "competitors", "lease costs",
        ],
    })


class LLMModel:
    name = "llm"

    def __init__(self, client=None, model_name: str | None = None, cache_dir: Path | None = None):
        if client is None:
            import anthropic
            client = anthropic.Anthropic(api_key=default_settings.anthropic_api_key)
        self._client = client
        self._model_name = model_name or default_settings.anthropic_model
        self._cache_dir = cache_dir or (default_settings.processed_dir / ".llm_cache")
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _decide_one(self, branch: BranchFeatures, network: NetworkStats, get_fallback) -> Decision:
        key = _cache_key(branch, self._model_name)
        cache_path = self._cache_dir / f"{key}.json"
        if cache_path.exists():
            return Decision(**json.loads(cache_path.read_text()))

        try:
            response = self._client.messages.create(
                model=self._model_name,
                max_tokens=1024,
                temperature=0,
                system=SYSTEM_PROMPT,
                tools=[DECISION_TOOL],
                tool_choice={"type": "tool", "name": "submit_decision"},
                messages=[{"role": "user", "content": _build_user_message(branch, network)}],
            )
            tool_block = next(b for b in response.content if b.type == "tool_use")
            # Never trust the LLM's echoed branch_id -- it's the join key used downstream by
            # /api/branches, and a typo'd/hallucinated id would silently break that join with
            # no error anywhere. Always use the branch_id we actually passed in.
            decision = Decision(**{**tool_block.input, "branch_id": branch.branch_id})
        except Exception as exc:  # noqa: BLE001 - deliberately broad, see comment below
            # Mirrors the "log loudly, fall back gracefully" philosophy used elsewhere in the
            # pipeline (branches.py, population.py, prices.py). A single branch's API call
            # failing (rate limit, network error, expired key, no tool-use block returned)
            # should not crash the whole run -- fall back to a rubric decision for just this
            # branch instead. The fallback decision is deliberately never cached: caching it
            # would permanently freeze a transient API failure as this branch's answer and the
            # API would never be retried on subsequent runs.
            logger.warning("model: LLM call failed for branch %s (%s), falling back to rubric",
                            branch.branch_id, exc)
            return get_fallback(branch)

        cache_path.write_text(json.dumps(decision.model_dump(), indent=2))
        return decision

    def decide(self, branches: list[BranchFeatures], network: NetworkStats) -> list[Decision]:
        # Lazily computed on first failure and memoized for the rest of this `decide()` call.
        # Must be keyed against the FULL batch of branches (not a single branch in isolation) --
        # RubricModel's top/bottom-third bucketing depends on how a branch ranks against its
        # peers, and a batch of one always lands that one branch in the PROTECT tier regardless
        # of its actual features.
        fallback_by_branch_id: dict[str, Decision] | None = None

        def get_fallback(branch: BranchFeatures) -> Decision:
            nonlocal fallback_by_branch_id
            if fallback_by_branch_id is None:
                from src.model.rubric import RubricModel
                fallback_by_branch_id = {
                    d.branch_id: d for d in RubricModel().decide(branches, network)
                }
            base = fallback_by_branch_id[branch.branch_id]
            # The fallback decision must be visibly distinguishable from a genuine LLM decision
            # -- a caller (or a human reading decisions.json) has no other way to know this
            # branch's decision didn't actually come from the LLM.
            return base.model_copy(update={
                "confidence": "low",
                "caveats": [*base.caveats,
                            "LLM call failed; rubric fallback used for this branch."],
            })

        return [self._decide_one(b, network, get_fallback) for b in branches]
