import pandas as pd
import pytest

from scripts.build_affluence import observed
from scripts.build_shop_rent import MIN_SHOP_M2, shop_area_rents


def _contract(area, amount, m2, usage="Commercial", sub="Shop", units=1):
    return {"AREA_EN": area, "ANNUAL_AMOUNT": amount, "ACTUAL_AREA": m2, "USAGE_EN": usage,
            "PROP_SUB_TYPE_EN": sub, "TOTAL_PROPERTIES": units}


def test_shop_rent_uses_single_shop_contracts_drops_kiosks_and_shrugs_off_an_outlier():
    rows = [_contract("A", 200_000, 100) for _ in range(98)]          # AED 2,000/m2
    rows += [_contract("A", 80_000, 3),                                  # kiosk: under MIN_SHOP_M2
             _contract("A", 9_000_000, 100),                             # mistyped: kept, median unmoved
             _contract("A", 200_000, 100, sub="Office"),                 # not a shop
             _contract("A", 200_000, 100, usage="Residential"),          # not commercial
             _contract("A", 900_000, 100, units=5)]                      # bulk lease
    got = shop_area_rents(pd.DataFrame(rows)).set_index("area").loc["A"]
    assert got.contracts == 99 and got.median_rent_m2 == pytest.approx(2000)
    assert MIN_SHOP_M2 == 10


def test_observed_takes_any_value_column_and_minimum():
    cells = pd.DataFrame([{"cell_id": "c", "emirate": "Dubai", "lat": 25.01, "lng": 55.01,
                           "south": 25.0, "north": 25.02, "west": 55.0, "east": 55.02}]).set_index("cell_id")
    areas = pd.DataFrame([{"area": "A", "lat": 25.01, "lng": 55.01, "contracts": 12, "median_rent_m2": 1500.0}])
    val, how = observed(cells, areas, col="median_rent_m2", min_contracts=10)
    assert val["c"] == 1500.0 and how["c"] == "inside"
    val, _ = observed(cells, areas, col="median_rent_m2", min_contracts=20)
    assert "c" not in val


def test_trim_is_per_area_so_a_dear_area_keeps_its_rent():
    # Review C1: a global 1% cut fell entirely on Downtown and halved its median; nothing is cut now.
    rows = [_contract("Cheap", 100_000, 100) for _ in range(1000)]                       # AED 1,000/m2
    rows += [_contract("Dear", 900_000 + i * 10_000, 100) for i in range(31)]            # 9,000-12,000/m2
    got = shop_area_rents(pd.DataFrame(rows)).set_index("area")
    assert got.loc["Dear"].median_rent_m2 == pytest.approx(10_500, rel=0.01)
