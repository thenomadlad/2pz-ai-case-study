from src.models import Branch
from src.acquire.prices import backfill_missing_prices


def _branch(id_: str, price: float | None) -> Branch:
    """Helper to create test branches."""
    return Branch(
        id=id_,
        name=f"Branch {id_}",
        lat=25.0,
        lng=55.0,
        area="Test Area",
        rating=None,
        review_count=None,
        avg_price_aed=price,
        source="seed"
    )


def test_backfill_uses_median_of_known_prices():
    branches = [_branch("a", 100.0), _branch("b", None), _branch("c", 200.0)]
    result, flagged = backfill_missing_prices(branches)
    assert result[0].avg_price_aed == 100.0
    assert result[1].avg_price_aed == 150.0  # median(100, 200)
    assert result[2].avg_price_aed == 200.0
    assert flagged == ["b"]


def test_backfill_noop_when_nothing_missing():
    branches = [_branch("a", 100.0), _branch("b", 150.0)]
    result, flagged = backfill_missing_prices(branches)
    assert all(result[i].avg_price_aed == branches[i].avg_price_aed for i in range(len(branches)))
    assert flagged == []


def test_backfill_uses_fallback_constant_when_all_prices_missing():
    branches = [_branch("a", None), _branch("b", None)]
    result, flagged = backfill_missing_prices(branches)
    assert all(b.avg_price_aed == 99.0 for b in result)
    assert flagged == ["a", "b"]
