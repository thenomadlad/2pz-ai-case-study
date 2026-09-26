import csv
import logging

from src.config import Settings, settings as default_settings
from src.models import Community

logger = logging.getLogger(__name__)


def _load_seed(seed_dir, global_female_share: float) -> list[Community]:
    path = seed_dir / "communities.csv"
    communities: list[Community] = []
    estimated_count = 0
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            total = int(row["population_total"])
            raw_female = row["population_female"]
            if raw_female:
                female = int(raw_female)
                is_estimated = False
            else:
                female = round(total * global_female_share)
                is_estimated = True
                estimated_count += 1
            communities.append(Community(
                id=row["id"],
                name_en=row["name_en"],
                lat=float(row["lat"]),
                lng=float(row["lng"]),
                population_total=total,
                population_female=female,
                is_estimated=is_estimated,
            ))
    logger.info("population: loaded %d communities from seed (%d with estimated female share)",
                len(communities), estimated_count)
    return communities


def _fetch_dubai_pulse() -> list[Community]:
    # Dubai Pulse open API integration is intentionally not implemented in
    # V0 — see docs/designs/2026-09-25-bedashing-v0-plan.md "Scope decisions".
    raise NotImplementedError


def load(settings: Settings | None = None, global_female_share: float = 0.49) -> list[Community]:
    settings = settings or default_settings
    if settings.dubai_pulse_enabled:
        try:
            return _fetch_dubai_pulse()
        except NotImplementedError:
            logger.warning("population: DUBAI_PULSE_ENABLED=1 but live enrichment isn't "
                            "implemented in V0, falling back to seed")
    return _load_seed(settings.seed_dir, global_female_share)
