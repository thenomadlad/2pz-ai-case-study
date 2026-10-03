import json
import logging

from src.acquire import branches as branches_mod
from src.acquire import population as population_mod
from src.acquire.prices import backfill_missing_prices
from src.config import Settings
from src.config import settings as default_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main(settings: Settings | None = None) -> None:
    settings = settings or default_settings
    settings.raw_dir.mkdir(parents=True, exist_ok=True)

    raw_branches = branches_mod.load(settings)
    filled_branches, price_flags = backfill_missing_prices(raw_branches, settings.fallback_price_aed)
    communities = population_mod.load(settings)

    (settings.raw_dir / "branches.json").write_text(
        json.dumps([b.model_dump() for b in filled_branches], indent=2))
    (settings.raw_dir / "price_flags.json").write_text(json.dumps(price_flags, indent=2))
    (settings.raw_dir / "communities.json").write_text(
        json.dumps([c.model_dump() for c in communities], indent=2))

    estimated_pop = sum(1 for c in communities if c.is_estimated)
    print("=== acquire summary ===")
    print(f"branches:    {len(filled_branches)} rows (source: "
          f"{'seed' if not settings.enable_scrape else 'seed, scrape unimplemented'})"
          f", {len(price_flags)} price(s) backfilled")
    print(f"communities: {len(communities)} rows "
          f"(source: {'seed' if not settings.dubai_pulse_enabled else 'seed, pulse unimplemented'})"
          f", {estimated_pop} with estimated female population")


if __name__ == "__main__":
    main()
