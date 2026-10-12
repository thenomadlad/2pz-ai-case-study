from src.baseline import run
from src.data_v3 import load_v3
from src.webapp.map import ACTION_COLORS, area_cells_layer, substitutes_layer
from src.webapp.pages.predictions import map_layers


def test_lounge_layer_colours_by_action_and_hollows_low_confidence():
    r = run()
    layer = next(x for x in map_layers(r, None, True) if x.id == "lounges")
    rows = {x["branch_id"]: x for x in layer.data}
    assert rows["zayed-international-airport"]["color"][:3] == ACTION_COLORS["NOT SCORED"]
    scored = [d for d in r.decisions if d.action != "NOT SCORED"]
    assert any(d.confidence == "low" for d in scored) and any(d.confidence != "low" for d in scored)
    for d in scored:   # filled in the call's colour; hollow (outlined in it) when low confidence
        row = rows[d.branch_id]
        if d.confidence == "low":
            assert row["color"][3] < 100 and row["line"] == ACTION_COLORS[d.action]
        else:
            assert row["color"] == [*ACTION_COLORS[d.action], 230]


def test_selected_lounge_adds_polygon_cells_and_substitutes():
    ids = lambda layers: [x.id for x in layers]
    none = ids(map_layers(run(), None, True))
    assert none == ["overlap", "areas", "lounges"]
    picked = map_layers(run(), "al-barsha", True)
    assert ids(picked) == ["overlap", "areas", "catchment-cells", "catchment-polygon", "substitutes", "lounges"]
    subs = next(x for x in picked if x.id == "substitutes").data
    assert len(subs) == next(f for f in run().features if f.branch_id == "al-barsha").substitutes_k
    assert "substitutes" not in ids(map_layers(run(), "al-barsha", False))


def test_area_layer_always_shows_every_area_coloured_by_what_it_is():
    from src.webapp.map import CAPTURED_MIN, GREY, GROW_BLUE, our_share
    r, cells = run(), load_v3().cells
    rows = area_cells_layer(cells, r.areas, r.area_decisions).data
    assert {row["area_id"] for row in rows} == {a.area_id for a in r.areas}           # nothing hidden
    act = {d.area_id: d.action for d in r.area_decisions}
    by = {a.area_id: a for a in r.areas}
    for row in rows:
        a = by[row["area_id"]]
        if act[a.area_id] == "GROW":
            assert row["shade"] == "GROW" and row["color"][:3] == GROW_BLUE
        elif our_share(a) >= CAPTURED_MIN:
            assert row["shade"] == "CAPTURED"
        elif act[a.area_id] == "SKIP":
            assert row["shade"] == "SKIP" and row["color"][:3] == GREY
    shades = {row["shade"] for row in rows}
    assert {"GROW", "CAPTURED", "SKIP"} <= shades
    deep = max((r_ for r_ in rows if r_["shade"] == "CAPTURED"), key=lambda r_: our_share(by[r_["area_id"]]))
    pale = min((r_ for r_ in rows if r_["shade"] == "CAPTURED"), key=lambda r_: our_share(by[r_["area_id"]]))
    assert deep["color"][1] < pale["color"][1]                                       # more served = deeper green
    one = area_cells_layer(cells, r.areas, r.area_decisions, only="kalba-sharjah").data
    assert {row["area_id"] for row in one} == {"kalba-sharjah"}


def test_substitutes_are_sized_by_reviews():
    rows = substitutes_layer([{"name": "a", "lat": 25, "lng": 55, "review_count": 16, "rating": 4.5,
                               "premium_because": "x"},
                              {"name": "b", "lat": 25, "lng": 55, "review_count": 1600, "rating": None,
                               "premium_because": "y"}]).data
    assert rows[0]["radius"] < rows[1]["radius"]


def test_pixel_units_serialise_as_literals_not_accessors():
    """Regression: a bare "pixels" became the accessor "@@=pixels", deck.gl fell back to meters
    and every marker filled the viewport."""
    import json

    from src.webapp.map import build_deck, lounge_layer
    r = run()
    sub = {"name": "a", "lat": 25, "lng": 55, "review_count": 16, "rating": 4.5, "premium_because": "x"}
    deck = json.loads(build_deck([lounge_layer(r.features, r.decisions), substitutes_layer([sub])]).to_json())
    layers = {x["id"]: x for x in deck["layers"]}
    assert layers["substitutes"]["radiusUnits"] == "pixels"
    assert layers["lounges"]["sizeUnits"] == "pixels"          # pins


def test_overlap_layer_marks_shared_cells_and_all_substitutes_are_deduplicated():
    r = run()
    layers = {x.id: x for x in map_layers(r, None, False, show_all_subs=True)}
    rows = layers["overlap"].data
    shared = [x for x in rows if "Reached by 1 " not in x["detail"]]
    assert shared and all(x["color"][0] == 211 for x in shared)
    assert len(rows) == load_v3().catchment.query("level == 'medium'").cell_id.nunique()
    names = [s["name"] for s in layers["all-substitutes"].data]
    assert len(names) > 0 and list(layers)[:2] == ["overlap", "all-substitutes"]

