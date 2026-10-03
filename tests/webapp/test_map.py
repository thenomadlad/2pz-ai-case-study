from src.models import BranchFeatures, Community, CommunityAssignment, Decision
from src.scenario.models import BranchDiffEntry, CommunityDiffEntry, ScenarioDiff
from src.webapp.map import (
    ACTION_COLORS,
    assignment_lines_layer,
    branch_layer,
    build_deck,
    community_layer,
    diff_highlight_layers,
    sibling_lines_layer,
)


def _feature(branch_id, lat, lng, pop=1000):
    return BranchFeatures(
        branch_id=branch_id, name=branch_id, lat=lat, lng=lng, female_pop_served=pop,
        communities_served=1, mean_distance_km=1.0, max_distance_km=1.0, contested_pop=0,
        contested_share=0.0, nearest_sibling_km=1.0, siblings_within_5km=0, avg_price_aed=100.0,
        price_index=1.0, rating=4.5, review_count=10, pop_per_1k_rank=1, estimated_fields=[],
    )


def test_branch_layer_colors_by_action():
    features = [_feature("a", 25.0, 55.0)]
    decisions = [Decision(branch_id="a", action="SHRINK", confidence="medium",
                           rationale="r", key_drivers=[], caveats=[])]
    layer = branch_layer(features, decisions)
    assert layer.data[0]["color"] == ACTION_COLORS["SHRINK"]
    assert layer.data[0]["branch_id"] == "a"


def test_community_layer_inherits_assigned_branch_action():
    communities = [Community(id="c1", name_en="C1", lat=25.01, lng=55.01,
                              population_total=1000, population_female=500, is_estimated=False)]
    assignments = [CommunityAssignment(community_id="c1", nearest_branch_id="a", nearest_km=1.0,
                                        second_branch_id=None, second_km=None, contested=False,
                                        female_pop=500)]
    layer = community_layer(communities, assignments, {"a": "PROTECT"})
    assert layer.data[0]["color"][:3] == ACTION_COLORS["PROTECT"]


def test_assignment_lines_layer_connects_community_to_branch():
    features = [_feature("a", 25.0, 55.0)]
    communities = [Community(id="c1", name_en="C1", lat=25.01, lng=55.01,
                              population_total=1000, population_female=500, is_estimated=False)]
    assignments = [CommunityAssignment(community_id="c1", nearest_branch_id="a", nearest_km=1.0,
                                        second_branch_id=None, second_km=None, contested=False,
                                        female_pop=500)]
    layer = assignment_lines_layer(communities, assignments, features)
    assert layer.data[0]["target"] == [55.0, 25.0]


def test_sibling_lines_layer_only_includes_branches_within_5km():
    selected = _feature("a", 25.0, 55.0)
    near = _feature("b", 25.01, 55.01)   # ~1.5km away
    far = _feature("c", 26.0, 56.0)      # far away
    layer = sibling_lines_layer(selected, [selected, near, far])
    targets = [row["target"] for row in layer.data]
    assert [near.lng, near.lat] in targets
    assert [far.lng, far.lat] not in targets


def test_diff_highlight_layers_separates_new_ring_and_relocation():
    features = [_feature("a", 25.0, 55.0)]
    diff = ScenarioDiff(
        scenario_name="s",
        branches=[
            BranchDiffEntry(branch_id="a", old={"action": "PROTECT", "lat": 25.0, "lng": 55.0},
                             new={"action": "SHRINK", "lat": 25.5, "lng": 55.5},
                             changed_fields={"lat": {"old": 25.0, "new": 25.5},
                                             "lng": {"old": 55.0, "new": 55.5}},
                             action_changed=True),
            BranchDiffEntry(branch_id="new-branch", old=None,
                             new={"action": "HOLD", "lat": 25.2, "lng": 55.2,
                                  "female_pop_served": 0},
                             changed_fields={}, action_changed=True),
        ],
        communities=[CommunityDiffEntry(community_id="c1", reassigned=False,
                                         old_branch_id="a", new_branch_id="a")],
        baseline_backend="rubric", current_backend="rubric",
    )
    layers = diff_highlight_layers(diff, features)
    ring_layer, new_layer, move_layer = layers
    assert len(ring_layer.data) == 1
    assert len(new_layer.data) == 1
    assert len(move_layer.data) == 1
    assert move_layer.data[0]["source"] == [55.0, 25.0]
    assert move_layer.data[0]["target"] == [55.5, 25.5]


def test_build_deck_assembles_layers():
    deck = build_deck([branch_layer([_feature("a", 25.0, 55.0)], [])])
    assert len(deck.layers) == 1


def _serialized_radius_units(layer) -> str:
    # pydeck treats a bare string kwarg as a per-row data accessor, serializing it as
    # "@@=<value>" -- which silently breaks deck.gl's unit lookup for a fixed enum value
    # like radius_units (deployed-and-reproduced bug: markers rendered ~2000x too large,
    # alpha-compositing into a single solid-color fill covering the whole map). Only a
    # quote-wrapped string ("'pixels'") survives as the literal "pixels". Checking the row
    # DATA a layer produces (what the other tests in this file check) can't catch this --
    # it's only visible in the actual serialized layer spec, which is what this asserts.
    import json
    spec = json.loads(build_deck([layer]).to_json())
    return spec["layers"][0]["radiusUnits"]


def test_branch_layer_radius_units_is_literal_pixels_not_an_accessor_expression():
    layer = branch_layer([_feature("a", 25.0, 55.0)], [])
    assert _serialized_radius_units(layer) == "pixels"


def test_community_layer_radius_units_is_literal_pixels_not_an_accessor_expression():
    community = Community(id="c1", name_en="C1", lat=25.01, lng=55.01,
                           population_total=1000, population_female=500, is_estimated=False)
    layer = community_layer([community], [], {})
    assert _serialized_radius_units(layer) == "pixels"


def test_diff_highlight_ring_and_new_branch_layers_radius_units_is_literal_pixels():
    diff = ScenarioDiff(
        scenario_name="s",
        branches=[
            BranchDiffEntry(branch_id="a", old={"action": "PROTECT", "lat": 25.0, "lng": 55.0},
                             new={"action": "SHRINK", "lat": 25.0, "lng": 55.0},
                             changed_fields={}, action_changed=True),
            BranchDiffEntry(branch_id="new-branch", old=None,
                             new={"action": "HOLD", "lat": 25.2, "lng": 55.2,
                                  "female_pop_served": 0},
                             changed_fields={}, action_changed=True),
        ],
        communities=[], baseline_backend="rubric", current_backend="rubric",
    )
    ring_layer, new_layer, _move_layer = diff_highlight_layers(diff, [_feature("a", 25.0, 55.0)])
    assert _serialized_radius_units(ring_layer) == "pixels"
    assert _serialized_radius_units(new_layer) == "pixels"
