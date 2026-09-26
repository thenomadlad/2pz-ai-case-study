import json
import logging

from src.config import Settings, settings as default_settings
from src.model.base import DecisionModel
from src.model.rubric import RubricModel
from src.models import BranchFeatures, NetworkStats

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def resolve_backend(settings: Settings) -> DecisionModel:
    if settings.model_backend == "llm":
        if not settings.anthropic_api_key:
            logger.warning("model: MODEL_BACKEND=llm but ANTHROPIC_API_KEY is unset, "
                            "falling back to rubric")
            return RubricModel()
        from src.model.llm import LLMModel
        return LLMModel()
    return RubricModel()


def main(settings: Settings | None = None) -> None:
    settings = settings or default_settings
    payload = json.loads((settings.processed_dir / "branch_features.json").read_text())
    network = NetworkStats(**payload["network"])
    branches = [BranchFeatures(**b) for b in payload["branches"]]

    model = resolve_backend(settings)
    decisions = model.decide(branches, network)

    (settings.processed_dir / "decisions.json").write_text(
        json.dumps([d.model_dump() for d in decisions], indent=2))
    (settings.processed_dir / "run_meta.json").write_text(
        json.dumps({"model_backend": model.name}, indent=2))

    print(f"model: backend={model.name}, wrote {len(decisions)} decisions")

    rubric_cache = settings.processed_dir / "decisions_rubric.json"
    if model.name == "rubric":
        rubric_cache.write_text(json.dumps([d.model_dump() for d in decisions], indent=2))
    elif rubric_cache.exists():
        rubric_decisions = {d["branch_id"]: d["action"]
                             for d in json.loads(rubric_cache.read_text())}
        llm_decisions = {d.branch_id: d.action for d in decisions}
        agree = sum(1 for bid, action in llm_decisions.items()
                     if rubric_decisions.get(bid) == action)
        print(f"model: llm vs rubric agreement on {agree}/{len(llm_decisions)} branches")
        for bid, action in llm_decisions.items():
            if rubric_decisions.get(bid) != action:
                print(f"  disagreement on {bid}: llm={action} rubric={rubric_decisions.get(bid)}")


if __name__ == "__main__":
    main()
