import yaml

from src.acquire import run as acquire_run
from src.config import Settings, settings as default_settings
from src.features import build as features_build
from src.model import run as model_run
from src.scenario.models import BaselineAssumptions


def load_baseline_assumptions(path) -> BaselineAssumptions:
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return BaselineAssumptions(**data.get("assumptions", {}))


def main(settings: Settings | None = None) -> None:
    settings = settings or default_settings
    scenarios_dir = settings.seed_dir.parent / "scenarios"
    assumptions = load_baseline_assumptions(scenarios_dir / "baseline.yaml")

    baseline_settings = settings.model_copy(update={
        "contest_ratio": assumptions.contest_ratio,
        "global_female_share": assumptions.global_female_share,
        "fallback_price_aed": assumptions.fallback_price_aed,
        "model_backend": assumptions.model_backend,
    })

    acquire_run.main(baseline_settings)
    features_build.main(baseline_settings)
    model_run.main(baseline_settings)


if __name__ == "__main__":
    main()
