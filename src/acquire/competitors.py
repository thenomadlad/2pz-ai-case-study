import csv
import logging

from src.config import Settings
from src.config import settings as default_settings
from src.models import Competitor

logger = logging.getLogger(__name__)


def load(settings: Settings | None = None) -> list[Competitor]:
    settings = settings or default_settings
    path = settings.seed_dir / "competitors.csv"
    if not path.exists():
        logger.warning("competitors: %s missing, competition signals will be zero", path)
        return []
    with open(path, newline="", encoding="utf-8") as f:
        competitors = [Competitor(id=r["id"], name=r["name"], category=r["category"],
                                  lat=float(r["lat"]), lng=float(r["lng"]))
                       for r in csv.DictReader(f)]
    logger.info("competitors: loaded %d rows from seed (OSM)", len(competitors))
    return competitors
