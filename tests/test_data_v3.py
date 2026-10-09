import pandas as pd

from src.config import Settings
from src.data_v3 import load_v3

V3 = Settings().v3_dir
LEVELS = ("low", "medium", "high")


def test_loads_the_v3_tables():
    v = load_v3()
    assert len(v.lounges) == 24 and len(v.cells) == 2373
    assert set(v.catchment.level) == set(LEVELS)
    assert not v.cells.adults.isna().any()
    for lo in v.lounges:
        assert all((lo.branch_id, m) in v.polygons for m in (10, 15, 20, 30, 40))


def test_salons_have_no_nan_in_market_fields():
    s = load_v3().salons
    assert s.review_count.dtype.kind == "i"
    assert not s.rating.map(lambda x: isinstance(x, float) and x != x).any()
    assert s.price_level.eq(s.price_level.fillna("")).all() and not s.price_level.isna().any()
    assert not s.excluded_reason.isna().any()
    assert all(not pd.isna(c["review_count"]) for cs in load_v3().candidates.values() for c in cs)


def test_candidates_nest_and_contain_the_15_min_record():
    v = load_v3()
    ids = lambda b, lv: {c["place_id"] for c in v.candidates[(b, lv)]}
    record = pd.read_csv(V3 / "lounge_candidates.csv").groupby("branch_id").place_id.apply(set)
    for lo in v.lounges:
        b = lo.branch_id
        assert ids(b, "low") <= ids(b, "medium") <= ids(b, "high")
        assert lo.place_id not in ids(b, "high")
        assert record[b] <= ids(b, "medium"), b


def test_full_share_at_15_min_matches_the_saturation_record():
    """Equal to the 15-min record wherever no growth circle touches the polygon."""
    v = load_v3()
    rec = pd.read_csv(V3 / "lounge_search_saturation.csv").set_index("branch_id")
    by = pd.read_csv(V3 / "lounge_search_saturation_by_level.csv")
    by = by[by.level == "medium"].set_index("branch_id")
    for lo in v.lounges:
        b = lo.branch_id
        assert v.full_share[(b, "medium")] == by.full_share[b]
        if by.circles[b] == rec.circles[b]:     # no growth circle over this polygon
            assert abs(by.full_share[b] - rec.full_share[b]) <= 0.005, b


def test_load_v3_accepts_explicit_settings():
    assert load_v3(Settings()) is load_v3()
