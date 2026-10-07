import csv
import logging

from src.config import Settings
from src.config import settings as default_settings
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


def load(settings: Settings | None = None) -> list[Community]:
    # Seed only: Dubai Pulse blocks automated access and publishes no per-community gender
    # split anyway (see docs/history.md, Data sources).
    settings = settings or default_settings
    return _load_seed(settings.seed_dir, settings.global_female_share)
