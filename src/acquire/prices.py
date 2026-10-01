import statistics

from src.models import Branch

FALLBACK_PRICE_AED = 99.0


def backfill_missing_prices(
    branches: list[Branch], fallback_price_aed: float = FALLBACK_PRICE_AED,
) -> tuple[list[Branch], list[str]]:
    known = [b.avg_price_aed for b in branches if b.avg_price_aed is not None]
    if not known:
        # All branches missing prices: apply fallback and flag all
        result = [b.model_copy(update={"avg_price_aed": fallback_price_aed}) for b in branches]
        flagged = [b.id for b in branches]
        return result, flagged

    median_price = statistics.median(known)
    flagged: list[str] = []
    result: list[Branch] = []
    for b in branches:
        if b.avg_price_aed is None:
            result.append(b.model_copy(update={"avg_price_aed": median_price}))
            flagged.append(b.id)
        else:
            result.append(b)
    return result, flagged
