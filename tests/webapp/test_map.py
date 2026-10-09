from src.baseline import run
from src.data_v3 import load_v3
from src.webapp.map import ACTION_COLORS, AREA_COLORS, area_cells_layer, substitutes_layer
from src.webapp.pages.overview import map_layers


def test_lounge_layer_colours_by_action_and_hollows_low_confidence():
    layer = next(x for x in map_layers(run(), None, True, False, True) if x.id == "lounges")
    rows = {r["branch_id"]: r for r in layer.data}
    assert rows["zayed-international-airport"]["color"][:3] == ACTION_COLORS["NOT SCORED"]
    assert rows["al-ain"]["color"] == [*ACTION_COLORS["PROTECT"], 230]           # high confidence
    assert rows["al-barsha"]["color"][3] < 100 and rows["al-barsha"]["line"] == ACTION_COLORS["HOLD"]


def test_selected_lounge_adds_polygon_cells_and_substitutes():
    ids = lambda layers: [x.id for x in layers]
    none = ids(map_layers(run(), None, True, False, True))
    assert none == ["areas", "lounges", "lounge-flags"]
    picked = map_layers(run(), "al-barsha", True, False, True)
    assert ids(picked) == ["areas", "catchment-cells", "catchment-polygon", "substitutes", "lounges", "lounge-flags"]
    subs = next(x for x in picked if x.id == "substitutes").data
    assert len(subs) == next(f for f in run().features if f.branch_id == "al-barsha").substitutes_k
    assert "substitutes" not in ids(map_layers(run(), "al-barsha", False, False, False))


def test_area_layer_hides_skip_unless_asked():
    r, cells = run(), load_v3().cells
    shown = {row["action"] for row in area_cells_layer(cells, r.areas, r.area_decisions).data}
    assert shown == {"GROW", "WATCH"}
    every = area_cells_layer(cells, r.areas, r.area_decisions, show_skip=True).data
    assert {row["action"] for row in every} == set(AREA_COLORS)
    one = area_cells_layer(cells, r.areas, r.area_decisions, only="kalba-sharjah").data
    assert {row["area_id"] for row in one} == {"kalba-sharjah"}


def test_substitutes_are_sized_by_reviews():
    rows = substitutes_layer([{"name": "a", "lat": 25, "lng": 55, "review_count": 16, "rating": 4.5,
                               "premium_because": "x"},
                              {"name": "b", "lat": 25, "lng": 55, "review_count": 1600, "rating": None,
                               "premium_because": "y"}]).data
    assert rows[0]["radius"] < rows[1]["radius"]
