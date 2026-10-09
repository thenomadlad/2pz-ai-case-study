from scripts.fetch_salons import capture, dedupe, excluded_reason, premium_substitutes, tag_bedashing


def cand(pid, reviews, rating=4.6, price=""):
    return {"place_id": pid, "review_count": reviews, "rating": rating, "price_level": price}


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


def test_bedashing_kept_and_joined():
    rows = [{"place_id": "g1", "name": "Bedashing Beauty Lounge Delma"},
            {"place_id": "g2", "name": "Pink Madi Beauty Salon"}]
    out = {r["place_id"]: r for r in tag_bedashing(rows, [{"place_id": "g1", "branch_id": "delma"}])}
    assert out["g1"]["is_bedashing"] and out["g1"]["branch_id"] == "delma"
    assert not out["g2"]["is_bedashing"] and not out["g2"]["branch_id"]


def test_dedupe_keeps_one_row_per_place():
    rows = [{"place_id": "a"}, {"place_id": "a"}, {"place_id": "b"}]
    assert [r["place_id"] for r in dedupe(rows)] == ["a", "b"]


def test_cached_lounge_is_not_rebilled(tmp_path, monkeypatch):
    from shapely.geometry import box
    import scripts.fetch_salons as f
    calls = []
    monkeypatch.setattr(f, "search", lambda body, **kw: calls.append(body) or {"places": []})
    branch = {"branch_id": "x", "lat": "25.0", "lng": "55.0"}
    f.fetch_lounge(branch, box(54.9, 24.9, 55.1, 25.1), tmp_path)
    f.fetch_lounge(branch, box(54.9, 24.9, 55.1, 25.1), tmp_path)
    assert len(calls) == 2                          # 2 queries, 1 page each, then cached


def test_circles_cover_area_and_skip_far_away():
    from shapely.geometry import Point, box
    from scripts.fetch_salons import circles
    area = box(55.0, 25.0, 55.05, 25.05)                     # ~5 x 5.5 km
    cs = circles(area, radius_m=1500)
    r_deg = 1500 / 111_000
    from math import cos, radians
    from shapely.affinity import scale
    # a 1,500 m circle in degrees: wider east-west than north-south at this latitude
    covered = [scale(Point(lng, lat).buffer(r_deg), xfact=1 / cos(radians(lat))) for lat, lng in cs]
    probes = [Point(55.0 + i * 0.005, 25.0 + j * 0.005) for i in range(11) for j in range(11)]
    assert all(any(c.contains(p) for c in covered) for p in probes)   # no gaps
    assert all(area.buffer(r_deg * 1.2).contains(Point(lng, lat)) for lat, lng in cs)  # none far away


def test_cached_circle_is_not_rebilled(tmp_path, monkeypatch):
    import scripts.fetch_salons as f
    calls = []
    monkeypatch.setattr(f, "search", lambda body, **kw: calls.append(body) or {"places": []})
    f.fetch_circle(25.0, 55.0, 1500, tmp_path)
    f.fetch_circle(25.0, 55.0, 1500, tmp_path)
    assert len(calls) == 1


def test_arabic_mens_salon_names_are_men_only():
    ok = {"status": "OPERATIONAL", "primary_type": "hair_salon"}
    assert excluded_reason(ok | {"name": "حلاق تركي hair cut"}) == "men-only"              # barber
    assert excluded_reason(ok | {"name": "صالون المشاهير للحلاقة الرجالية"}) == "men-only"  # men's
    assert excluded_reason(ok | {"name": "صالون نونه ستايل للسيدات"}) == ""               # ladies'


def test_coverage_k_takes_salons_until_share_reached():
    from scripts.fetch_salons import coverage_k
    subs = [{"review_count": r} for r in (500, 300, 100, 100)]   # 1,000 reviews
    assert coverage_k(subs, 0.5) == 1     # 500 = 50%
    assert coverage_k(subs, 0.6) == 2     # 800 >= 600
    assert coverage_k(subs, 1.0) == 4
    assert coverage_k([], 0.6) == 0


def test_recall_multiplier_scales_with_saturation():
    from scripts.fetch_salons import recall_multiplier
    assert recall_multiplier(0.0, 0.66) == 1.0                 # nothing truncated: no correction
    assert round(recall_multiplier(1.0, 0.66), 3) == round(1 / 0.66, 3)
    assert round(recall_multiplier(0.5, 0.5), 3) == 1.5


def test_capture_by_coverage_applies_multiplier():
    from scripts.fetch_salons import capture_by_coverage
    premium = [{"review_count": r} for r in (600, 300, 100)]   # sorted by reviews
    cap, k = capture_by_coverage(100, premium, coverage=0.6, multiplier=1.0)
    assert k == 1 and cap == 100 / 700
    cap, k = capture_by_coverage(100, premium, coverage=0.6, multiplier=1.5)
    assert k == 1 and cap == 100 / (100 + 900)
    assert capture_by_coverage(100, [], 0.6, 1.3) == (1.0, 0)


def test_growth_cells_are_populated_and_outside_every_catchment():
    import pandas as pd
    from scripts.fetch_salons import growth_cells
    women = pd.Series({"in": 9000.0, "big": 5000.0, "small": 500.0})
    catchment = pd.DataFrame({"cell_id": ["in"], "level": ["medium"], "branch_id": ["x"]})
    assert growth_cells(women, catchment, level="medium", min_women=2000) == ["big"]
