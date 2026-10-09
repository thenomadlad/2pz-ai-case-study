from scripts.fetch_salons import dedupe, tag_bedashing


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


def test_growth_cells_are_populated_and_outside_every_catchment():
    import pandas as pd
    from scripts.fetch_salons import growth_cells
    women = pd.Series({"in": 9000.0, "big": 5000.0, "small": 500.0})
    catchment = pd.DataFrame({"cell_id": ["in"], "level": ["medium"], "branch_id": ["x"]})
    assert growth_cells(women, catchment, level="medium", min_women=2000) == ["big"]
