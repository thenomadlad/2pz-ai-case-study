import csv
import logging

from src.config import Settings
from src.config import settings as default_settings
from src.models import Branch

logger = logging.getLogger(__name__)


def _load_seed(seed_dir) -> list[Branch]:
    path = seed_dir / "branches.csv"
    branches: list[Branch] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            branches.append(Branch(
                id=row["id"],
                name=row["name"],
                lat=float(row["lat"]),
                lng=float(row["lng"]),
                area=row["area"],
                rating=float(row["rating"]) if row["rating"] else None,
                review_count=int(row["review_count"]) if row["review_count"] else None,
                avg_price_aed=float(row["avg_price_aed"]) if row["avg_price_aed"] else None,
                source="seed",
            ))
    logger.info("branches: loaded %d rows from seed", len(branches))
    return branches


def load(settings: Settings | None = None) -> list[Branch]:
    # Seed only: branches were hand-collected from 2GIS (see docs/history.md, Data sources).
    settings = settings or default_settings
    return _load_seed(settings.seed_dir)
