"""One-off: commercial (shop) rent per ~2 km cell, Dubai only, from DLD Ejari contracts.

Same file and same area -> point -> cell pipeline as the residential rents (scripts/build_affluence.py),
filtered to single-unit commercial shops of MIN_SHOP_M2+ m2; the per-area median is robust to a
mistyped contract, so nothing is trimmed (a 1% trim, overall or per area, cut real rents: Downtown
halved, small areas emptied). Shop rent is OUR COST (a lounge's site), not customer affluence: keep it apart from
affluence_rent.

Outputs (data/seed/v3/): dubai_shop_rents_by_area.csv, cell_shop_rent.csv
(cell_id, shop_rent_m2, assignment: inside | nearest).

Run: uv run --extra notebook python scripts/build_shop_rent.py
"""
import glob
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.build_affluence import RAW, V3, locate, observed

MIN_SHOP_M2 = 10
MIN_SHOP_CONTRACTS = 10
WHY = {
    "MIN_SHOP_M2": "Under 10 m2 is a kiosk or counter: its AED/m2 runs several times a shop's.",
    "MIN_SHOP_CONTRACTS": ("Shops are rarer than homes (13.6k vs 251k contracts in 3 months), so an "
                           "area needs 10, not 20, to get a median."),
}


def shop_area_rents(rents: pd.DataFrame) -> pd.DataFrame:
    """Median AED/m2/yr per DLD area over single-unit shop contracts of MIN_SHOP_M2+ m2."""
    r = rents[(rents.USAGE_EN == "Commercial") & (rents.PROP_SUB_TYPE_EN.str.strip() == "Shop")
              & (rents.TOTAL_PROPERTIES.fillna(1) == 1) & (rents.ANNUAL_AMOUNT > 0)
              & (rents.ACTUAL_AREA >= MIN_SHOP_M2)]
    r = r.assign(m2=r.ANNUAL_AMOUNT / r.ACTUAL_AREA)
    return (r.groupby("AREA_EN").agg(contracts=("m2", "size"), median_rent_m2=("m2", "median"))
            .reset_index().rename(columns={"AREA_EN": "area"}))


def main() -> None:
    rents = pd.concat(pd.read_csv(f, encoding="utf-8-sig", low_memory=False)
                      for f in sorted(glob.glob(str(RAW / "dld" / "rents-*.csv"))))
    areas = locate(shop_area_rents(rents))
    areas.to_csv(V3 / "dubai_shop_rents_by_area.csv", index=False)
    cells = pd.read_csv(V3 / "cells.csv").set_index("cell_id")
    val, how = observed(cells, areas, col="median_rent_m2", min_contracts=MIN_SHOP_CONTRACTS)
    out = pd.DataFrame({"shop_rent_m2": val.round(0), "assignment": how})
    out.index.name = "cell_id"
    out.to_csv(V3 / "cell_shop_rent.csv")
    located = areas.match != "unmatched"
    print(f"{areas.contracts.sum():,} shop contracts; {located.sum()}/{len(areas)} areas located "
          f"({areas.contracts[located].sum() / areas.contracts.sum():.0%} of contracts); "
          f"shop rent for {len(out)} Dubai cells; median {out.shop_rent_m2.median():,.0f} AED/m2/yr")


if __name__ == "__main__":
    main()
