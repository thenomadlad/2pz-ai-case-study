from shapely.geometry import Polygon

from scripts.fetch_isochrones import batches, ranges_minutes, reaches


def test_reaches_returns_points_inside_only():
    square = Polygon([(55.0, 25.0), (55.1, 25.0), (55.1, 25.1), (55.0, 25.1)])
    pts = {"in": (25.05, 55.05), "out": (25.2, 55.2)}   # (lat, lng)
    assert reaches(square, pts) == ["in"]


def test_ranges_cover_catchments_and_2x_competitor_bounds():
    # 2 x low (20) is already the high catchment, so it isn't repeated.
    assert ranges_minutes({"low": 10, "medium": 15, "high": 20}) == [10, 15, 20, 30, 40]


def test_batches_of_five_locations():
    assert [len(b) for b in batches(list(range(12)), 5)] == [5, 5, 2]
