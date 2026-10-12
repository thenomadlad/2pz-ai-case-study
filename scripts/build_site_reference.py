"""One-off: the frozen market of salon SITES that lounge and area labels are judged against.

Reference set = every real (non-imputed) premium competitor salon the served model uses
(src/model/served._competitors; Bedashing excluded), at baseline assumptions and default levels.
Per site: its cell, emirate and cell shop rent, and ref_served = the women a typical lounge (median
reviews and rating of the scored lounges, as the what-ifs) would serve at that point with all our
lounges open (served.what_if_open). Frozen: nothing we open or close moves it. Rebuild (and say so)
only when the served model, the demand or the salon data change.

Output: data/seed/v3/site_reference.csv. Run: uv run python scripts/build_site_reference.py (~25 s).
"""
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.config import REPO_ROOT, load_baseline_assumptions  # noqa: E402
from src.data_v3 import load_v3  # noqa: E402
from src.features import lounges as L  # noqa: E402
from src.market import affluence_weight, women_15plus  # noqa: E402
from src.model import served as S  # noqa: E402
from src.models import Levels  # noqa: E402

OUT = ROOT / "data/seed/v3/site_reference.csv"


def main():
    t0 = time.perf_counter()
    v3, lv = load_v3(), Levels()
    a = load_baseline_assumptions(REPO_ROOT / "data" / "scenarios" / "baseline.yaml")
    women = women_15plus(v3.cells, v3.emirates, a.worker_housing_female_share[lv.worker_share])
    aw = women * affluence_weight(v3.cells.rent_observed, women, a.affluence_elasticity[lv.affluence])
    reviews, rating = L.TYPICAL_REVIEWS, L.TYPICAL_RATING
    comp = S._competitors(v3, a)
    real = comp[~comp.id.str.startswith("IMP:")]
    c = v3.cells
    slat, slng = real.lat.to_numpy()[:, None], real.lng.to_numpy()[:, None]
    inbox = ((c.south.to_numpy() <= slat) & (slat < c.north.to_numpy())
             & (c.west.to_numpy() <= slng) & (slng < c.east.to_numpy()))
    rows = []
    for (pid, lat, lng), i, ok in zip(real[["id", "lat", "lng"]].itertuples(index=False), inbox.argmax(1), inbox.any(1)):
        if not ok:
            continue
        cell = c.index[i]
        w = S.what_if_open(v3, a, aw, lat, lng, reviews, rating, not_scored=frozenset(L.NOT_SCORED))
        rows.append({"place_id": pid, "emirate": c.emirate.iloc[i], "cell_id": cell, "lat": lat, "lng": lng,
                     "shop_rent_m2": round(float(c.shop_rent_m2.iloc[i]), 1), "ref_served": round(w["served"], 1)})
    df = pd.DataFrame(rows)
    note = (f"# Frozen {date.today()} by scripts/build_site_reference.py: real premium competitor salons "
            f"(served._competitors, no imputed, no Bedashing) at baseline levels; typical lounge {reviews:g} "
            f"reviews, {rating} stars; what_if_open with all lounges open. {len(df)} of {len(real)} sites in a cell.\n")
    OUT.write_text(note + df.to_csv(index=False))
    m = df.groupby("emirate").shop_rent_m2.median()
    ratio = df.emirate.map(m) / df.shop_rent_m2
    print(df.groupby("emirate").agg(n=("place_id", "size"), median_rent=("shop_rent_m2", "median"),
                                    median_served=("ref_served", "median")).to_string())
    print(f"rent_ratio P10 {np.percentile(ratio, 10):.4f} P90 {np.percentile(ratio, 90):.4f}")
    print(f"{len(df)} sites in {time.perf_counter() - t0:.1f} s -> {OUT}")


if __name__ == "__main__":
    main()
