from src.market import (
    capture,
    capture_by_coverage,
    coverage_k,
    excluded_reason,
    market_women,
    premium_substitutes,
    recall_multiplier,
    residential_share,
    women_15plus,
)


def cand(pid, reviews, rating=4.6, price=""):
    return {"place_id": pid, "review_count": reviews, "rating": rating, "price_level": price}


def test_residential_share_rebalances_to_emirate_total():
    # 1,000 adults, 300 of them women; 200 adults in worker housing at 5% female.
    s = residential_share(women=300, adults=1000, worker_adults=200, worker_share=0.05)
    assert round(s, 4) == round((300 - 10) / 800, 4)
    assert round(0.05 * 200 + s * 800) == 300   # the emirate total is preserved


def test_residential_share_clipped_to_valid_range():
    assert residential_share(women=10, adults=100, worker_adults=90, worker_share=0.5) == 0.0
    assert residential_share(women=100, adults=100, worker_adults=0, worker_share=0.05) == 1.0


def test_market_women_splits_worker_and_residential():
    assert market_women(adults=1000, worker_adults=400, worker_share=0.05,
                        resid_share=0.45) == 0.05 * 400 + 0.45 * 600


def test_women_15plus_keeps_each_emirate_total():
    import pandas as pd
    cells = pd.DataFrame({"emirate": ["Dubai", "Dubai"], "adults": [1000, 1000],
                          "adults_worker": [800, 0], "women_worldpop": [336, 336]})
    emirates = pd.DataFrame({"adults": [2000], "women_worldpop": [672], "worker_adults": [800]},
                            index=["Dubai"])
    w = women_15plus(cells, emirates, worker_share=0.05)
    assert round(w.sum()) == 672           # same women, moved between cells
    assert w[0] < 336 < w[1]               # out of worker housing, into the residential cell


def test_premium_takes_priced_premium_and_popular_well_rated_unpriced():
    c = [cand("a", 50, price="expensive"),          # priced premium: in, whatever its reviews
         cand("b", 10, price="moderate"),           # priced below: out
         cand("c", 900), cand("d", 300),            # unpriced, popular and well rated: in
         cand("e", 400, rating=4.0),                # popular but rated below 4.3: out
         cand("f", 5)]                              # unpriced, below the median: out
    got = [x["place_id"] for x in premium_substitutes(c, k=20, min_rating=4.3,
                                                      price_levels=["expensive", "very_expensive"])]
    assert got == ["c", "d", "a"]                   # ranked by reviews


def test_premium_caps_at_k():
    c = [cand(str(i), 1000 - i) for i in range(30)]
    assert len(premium_substitutes(c, k=10, min_rating=4.3, price_levels=["expensive"])) == 10


def test_missing_reviews_and_rating_never_premium_stand_in():
    c = [cand("x", None, rating=None), cand("y", 100)]
    assert [x["place_id"] for x in premium_substitutes(c, 20, 4.3, ["expensive"])] == ["y"]


def test_capture_and_no_substitutes():
    assert capture(300, [{"review_count": 600}, {"review_count": 300}]) == 0.25
    assert capture(300, []) == 1.0


def test_excluded_reason():
    ok = {"name": "Pink Lady Salon", "status": "OPERATIONAL", "primary_type": "beauty_salon"}
    assert excluded_reason(ok) == ""
    assert excluded_reason(ok | {"name": "Royal Gents Salon"}) == "men-only"
    assert excluded_reason(ok | {"primary_type": "barber_shop"}) == "men-only"
    assert excluded_reason(ok | {"primary_type": "dental_clinic"}) == "not-a-salon"
    assert excluded_reason(ok | {"status": "CLOSED_PERMANENTLY"}) == "not-operational"


def test_arabic_mens_salon_names_are_men_only():
    ok = {"status": "OPERATIONAL", "primary_type": "hair_salon"}
    assert excluded_reason(ok | {"name": "حلاق تركي hair cut"}) == "men-only"              # barber
    assert excluded_reason(ok | {"name": "صالون المشاهير للحلاقة الرجالية"}) == "men-only"  # men's
    assert excluded_reason(ok | {"name": "صالون نونه ستايل للسيدات"}) == ""               # ladies'


def test_coverage_k_takes_salons_until_share_reached():
    subs = [{"review_count": r} for r in (500, 300, 100, 100)]   # 1,000 reviews
    assert coverage_k(subs, 0.5) == 1     # 500 = 50%
    assert coverage_k(subs, 0.6) == 2     # 800 >= 600
    assert coverage_k(subs, 1.0) == 4
    assert coverage_k([], 0.6) == 0


def test_recall_multiplier_scales_with_saturation():
    assert recall_multiplier(0.0, 0.66) == 1.0                 # nothing truncated: no correction
    assert round(recall_multiplier(1.0, 0.66), 3) == round(1 / 0.66, 3)
    assert round(recall_multiplier(0.5, 0.5), 3) == 1.5


def test_capture_by_coverage_applies_multiplier():
    premium = [{"review_count": r} for r in (600, 300, 100)]   # sorted by reviews
    cap, k = capture_by_coverage(100, premium, coverage=0.6, multiplier=1.0)
    assert k == 1 and cap == 100 / 700
    cap, k = capture_by_coverage(100, premium, coverage=0.6, multiplier=1.5)
    assert k == 1 and cap == 100 / (100 + 900)
    assert capture_by_coverage(100, [], 0.6, 1.3) == (1.0, 0)


def _aff():
    import pandas as pd
    rent = pd.Series([50_000, 100_000, 200_000, 4_000_000, float("nan")], index=list("abcde"))
    women = pd.Series([1000, 2000, 1000, 10, 5000], index=list("abcde"))
    return rent, women


def test_affluence_weight_normalises_to_women_weighted_mean_one():
    from src.market import affluence_weight
    rent, women = _aff()
    for e in (0.5, 1.0):
        w = affluence_weight(rent, women, e)
        obs = rent.notna()
        assert abs((w[obs] * women[obs]).sum() / women[obs].sum() - 1) < 1e-12
        assert w["a"] < w["b"] < w["c"]                     # richer cells weigh more


def test_affluence_weight_clips_before_rescaling():
    from src.market import affluence_weight
    rent, women = _aff()
    w = affluence_weight(rent, women, 1.0)
    # median 100k: d's ratio 40 clips to 4, so after rescaling d / b == 4 exactly
    assert abs(w["d"] / w["b"] - 4) < 1e-12 and abs(w["a"] / w["b"] - 0.5) < 1e-12


def test_affluence_weight_neutral_without_rent_or_elasticity():
    from src.market import affluence_weight
    rent, women = _aff()
    assert affluence_weight(rent, women, 1.0)["e"] == 1.0  # no observed rent: neutral
    off = affluence_weight(rent, women, 0)
    assert (off == 1.0).all() and list(off.index) == list(rent.index)


def test_weighted_median():
    from src.market import weighted_median
    assert weighted_median([1, 2, 3], [1, 1, 5]) == 3
    assert weighted_median([1, 2, 3], [5, 1, 1]) == 1
    assert weighted_median([float("nan")], [1]) is None and weighted_median([], []) is None
