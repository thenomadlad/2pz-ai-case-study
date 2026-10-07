"""pydeck layer builders for the Dubai branch map. st.pydeck_chart (wired in
src/webapp/pages/product.py) renders whatever Deck build_deck() assembles.

Radii are in pixels (radius_units=_PIXELS), not meters, mirroring the previous Leaflet
circleMarker sizing -- zoom-invariant marker size, same visual language as before.

pydeck treats any bare string kwarg as a per-row data accessor (serialized as a
"@@=<value>" JS expression) UNLESS the string is itself wrapped in quote characters, in
which case it strips them and passes the literal through -- see
pydeck.bindings.layer.Layer.__init__. radius_units is a fixed enum value, not a per-row
field, so it must be passed as a literal via _PIXELS ("'pixels'"), not a bare "pixels":
passing the bare string silently produced "@@=pixels" on the wire, which deck.gl
couldn't evaluate as a unit, so it fell back to its default (CommonUnits) -- at this
map's zoom level that's roughly 2000x too large per radius unit, so every marker
rendered large enough to fill (and alpha-composite across) the entire viewport.
"""
import math

import pydeck as pdk

from src.models import (
    BranchFeatures,
    Community,
    CommunityAssignment,
    CommunityFeatures,
    Competitor,
    Decision,
    OpportunityDecision,
)
from src.scenario.models import ScenarioDiff

ACTION_COLORS: dict[str, list[int]] = {
    "PROTECT": [46, 125, 50],
    "HOLD": [249, 168, 37],
    "SHRINK": [198, 40, 40],
}
OPPORTUNITY_COLORS: dict[str, list[int]] = {
    "GROW": [21, 101, 192],
    "WATCH": [142, 36, 170],
    "SKIP": [189, 189, 189],
}
DEFAULT_COLOR = [153, 153, 153]
DUBAI_VIEW = pdk.ViewState(latitude=25.2048, longitude=55.2708, zoom=11)

# Quote-wrapped so pydeck passes the literal string "pixels" through to deck.gl instead of
# treating it as a per-row accessor expression -- see the module docstring above.
_PIXELS = "'pixels'"


def _pop_radius(pop: float) -> float:
    return max(6.0, min(30.0, math.sqrt(max(pop, 0)) / 8))


def branch_layer(features: list[BranchFeatures], decisions: list[Decision]) -> pdk.Layer:
    decisions_by_id = {d.branch_id: d for d in decisions}
    rows = []
    for f in features:
        decision = decisions_by_id.get(f.branch_id)
        action = decision.action if decision else "HOLD"
        rows.append({
            "branch_id": f.branch_id, "name": f.name, "lat": f.lat, "lng": f.lng,
            "action": action, "radius": _pop_radius(f.female_pop_served),
            "color": ACTION_COLORS.get(action, DEFAULT_COLOR),
        })
    return pdk.Layer(
        "ScatterplotLayer", data=rows, get_position=["lng", "lat"], get_radius="radius",
        radius_units=_PIXELS, get_fill_color="color", pickable=True, id="branches",
    )


def community_layer(communities: list[Community], assignments: list[CommunityAssignment],
                     branch_actions: dict[str, str]) -> pdk.Layer:
    assignment_by_id = {a.community_id: a for a in assignments}
    rows = []
    for c in communities:
        assignment = assignment_by_id.get(c.id)
        action = branch_actions.get(assignment.nearest_branch_id) if assignment else None
        color = ACTION_COLORS.get(action, DEFAULT_COLOR)
        pop = assignment.female_pop if assignment else 0
        opacity = min(1.0, max(0.2, pop / 20000))
        rows.append({"lat": c.lat, "lng": c.lng, "color": [*color, int(opacity * 255)]})
    return pdk.Layer(
        "ScatterplotLayer", data=rows, get_position=["lng", "lat"], get_radius=4,
        radius_units=_PIXELS, get_fill_color="color", id="communities",
    )


def assignment_lines_layer(communities: list[Community], assignments: list[CommunityAssignment],
                            features: list[BranchFeatures]) -> pdk.Layer:
    branch_by_id = {f.branch_id: f for f in features}
    community_by_id = {c.id: c for c in communities}
    rows = []
    for a in assignments:
        branch = branch_by_id.get(a.nearest_branch_id)
        community = community_by_id.get(a.community_id)
        if not branch or not community:
            continue
        rows.append({"source": [community.lng, community.lat], "target": [branch.lng, branch.lat]})
    return pdk.Layer(
        "LineLayer", data=rows, get_source_position="source", get_target_position="target",
        get_color=[136, 136, 136], get_width=1, id="assignment-lines",
    )


def sibling_lines_layer(selected: BranchFeatures, features: list[BranchFeatures]) -> pdk.Layer:
    rows = []
    for other in features:
        if other.branch_id == selected.branch_id:
            continue
        km = math.hypot(selected.lat - other.lat, selected.lng - other.lng) * 111
        if km <= 5.0:
            rows.append({"source": [selected.lng, selected.lat],
                         "target": [other.lng, other.lat]})
    return pdk.Layer(
        "LineLayer", data=rows, get_source_position="source", get_target_position="target",
        get_color=[85, 85, 85], get_width=1, id="sibling-lines",
    )


def diff_highlight_layers(diff: ScenarioDiff, features: list[BranchFeatures]) -> list[pdk.Layer]:
    feature_by_id = {f.branch_id: f for f in features}
    ring_rows, new_rows, move_rows = [], [], []

    for entry in diff.branches:
        if entry.old is None and entry.new is not None:
            new_rows.append({
                "lat": entry.new["lat"], "lng": entry.new["lng"],
                "color": [*ACTION_COLORS.get(entry.new["action"], DEFAULT_COLOR), 140],
            })
            continue
        if not (entry.action_changed or entry.changed_fields):
            continue
        branch = feature_by_id.get(entry.branch_id)
        if branch is None:
            continue
        color = ACTION_COLORS.get(entry.new["action"], [0, 0, 0]) if entry.action_changed else [0, 0, 0]
        ring_rows.append({
            "lat": branch.lat, "lng": branch.lng,
            "radius": _pop_radius(branch.female_pop_served) + 6, "color": color,
        })
        lat_change = entry.changed_fields.get("lat")
        lng_change = entry.changed_fields.get("lng")
        if lat_change or lng_change:
            old_lat = lat_change["old"] if lat_change else branch.lat
            old_lng = lng_change["old"] if lng_change else branch.lng
            move_rows.append({
                "source": [old_lng, old_lat],
                "target": [entry.new["lng"], entry.new["lat"]],
            })

    return [
        pdk.Layer("ScatterplotLayer", data=ring_rows, get_position=["lng", "lat"],
                  get_radius="radius", radius_units=_PIXELS, filled=False, stroked=True,
                  get_line_color="color", line_width_min_pixels=3, id="diff-rings"),
        pdk.Layer("ScatterplotLayer", data=new_rows, get_position=["lng", "lat"], get_radius=10,
                  radius_units=_PIXELS, get_fill_color="color", id="diff-new-branches"),
        pdk.Layer("LineLayer", data=move_rows, get_source_position="source",
                  get_target_position="target", get_color=[21, 101, 192], get_width=2,
                  id="diff-relocations"),
    ]


def opportunity_layer(communities: list[CommunityFeatures],
                      opportunities: list[OpportunityDecision]) -> pdk.Layer:
    action_by_id = {o.community_id: o.action for o in opportunities}
    rows = []
    for c in communities:
        action = action_by_id.get(c.community_id, "SKIP")
        rows.append({
            "community_id": c.community_id, "name": c.name, "lat": c.lat, "lng": c.lng,
            "action": action, "radius": 9 if action == "GROW" else 7,
            "color": [*OPPORTUNITY_COLORS[action], 90 if action == "SKIP" else 200],
        })
    return pdk.Layer(
        "ScatterplotLayer", data=rows, get_position=["lng", "lat"], get_radius="radius",
        radius_units=_PIXELS, get_fill_color="color", pickable=True, stroked=True,
        get_line_color=[255, 255, 255], line_width_min_pixels=1, id="opportunities",
    )


def competitor_layer(competitors: list[Competitor]) -> pdk.Layer:
    rows = [{"name": k.name or "(unnamed salon)", "action": "competitor",
             "lat": k.lat, "lng": k.lng} for k in competitors]
    return pdk.Layer(
        "ScatterplotLayer", data=rows, get_position=["lng", "lat"], get_radius=2,
        radius_units=_PIXELS, get_fill_color=[66, 66, 66, 140], pickable=True,
        id="competitors",
    )


def build_deck(layers: list[pdk.Layer]) -> pdk.Deck:
    return pdk.Deck(
        layers=layers, initial_view_state=DUBAI_VIEW, map_style=None,
        tooltip={"html": "<b>{name}</b><br/>{action}"},
    )
