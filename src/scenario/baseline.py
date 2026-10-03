import shutil

import yaml

from src.acquire import run as acquire_run
from src.config import Settings
from src.config import settings as default_settings
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

    # A stale data/processed/current/ (and its diff.json) must never survive a baseline
    # regeneration -- otherwise /api/diff keeps serving a comparison against a baseline
    # that no longer exists on disk, with no indication to the user that it's stale.
    current_dir = settings.processed_dir.parent / "current"
    shutil.rmtree(current_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
