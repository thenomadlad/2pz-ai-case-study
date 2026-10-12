"""pydeck layer builders for the UAE maps. Every pickable layer's rows carry `name` and `detail`,
which the shared tooltip shows.

Radii are in pixels. pydeck treats a bare string kwarg as a per-row accessor unless it is wrapped
in quotes, so fixed enum values go in as _PIXELS ("'pixels'"); a bare "pixels" silently fell back
to meters and filled the viewport."""
import base64
import math

import pandas as pd
import pydeck as pdk

from src.model import growth
from src.models import Area, AreaDecision, Decision, LoungeFeatures

ACTION_COLORS: dict[str, list[int]] = {
    "PROTECT": [46, 125, 50], "HOLD": [249, 168, 37], "SHRINK": [198, 40, 40],
    "NOT SCORED": [140, 140, 140],
}
AREA_COLORS: dict[str, list[int]] = {"GROW": [21, 101, 192], "WATCH": [142, 36, 170], "SKIP": [176, 176, 176]}
UAE_VIEW = pdk.ViewState(latitude=24.6, longitude=54.6, zoom=6.4)
_PIXELS = "'pixels'"

_PIN_PATH = "M24 2C12.4 2 3 11.2 3 22.6 3 38 24 62 24 62s21-24 21-39.4C45 11.2 35.6 2 24 2z"


def pin_icon(rgb: list[int], hollow: bool = False) -> dict:
    """A map-app style pin in the call's colour; hollow (white, outlined in the colour) for low confidence."""
    c = "#{:02x}{:02x}{:02x}".format(*rgb)
    body, dot = ("#fff", c) if hollow else (c, "#fff")
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="48" height="64" viewBox="0 0 48 64">'
           f'<path d="{_PIN_PATH}" fill="{body}" stroke="{c if hollow else "#fff"}" stroke-width="3"/>'
           f'<circle cx="24" cy="22.5" r="8" fill="{dot}"/></svg>')
    return {"url": "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode(),
            "width": 48, "height": 64, "anchorX": 24, "anchorY": 62, "id": f"pin-{c}-{hollow}"}


def _box(cells: pd.DataFrame, cid: str) -> list[list[float]]:
    c = cells.loc[cid]
    return [[c.west, c.south], [c.east, c.south], [c.east, c.north], [c.west, c.north]]


def lounge_layer(features: list[LoungeFeatures], decisions: list[Decision],
                 only: set[str] | None = None) -> pdk.Layer:
    """A pin per lounge in its call's colour; hollow pin for low confidence. `only`: just these lounges."""
    by_id = {d.branch_id: d for d in decisions}
    rows = []
    for f in features:
        if only is not None and f.branch_id not in only:
            continue
        d = by_id[f.branch_id]
        color = ACTION_COLORS[d.action]
        low = d.confidence == "low" and d.action != "NOT SCORED"
        comp = "" if d.action == "NOT SCORED" else f" · composite {d.composite:.2f}"
        rows.append({
            "branch_id": f.branch_id, "name": f.name, "lat": f.lat, "lng": f.lng, "action": d.action,
            "color": [*color, 50 if low else 230], "line": color if low else [255, 255, 255],
            "icon": pin_icon(color, low),
            "detail": (f"{d.action}{comp} · confidence {'n/a' if d.action == 'NOT SCORED' else d.confidence}<br/>"
                       f"{f.catchment_women:,.0f} women in catchment · "
                       f"{f.rating or 'no'}★ · {f.review_count:,} reviews"),
        })
    return pdk.Layer("IconLayer", data=rows, get_position=["lng", "lat"], get_icon="icon", get_size=34,
                     size_units=_PIXELS, pickable=True, id="lounges")


def polygon_layer(geometry: dict, minutes: int, name: str) -> pdk.Layer:
    """A lounge's drive-time polygon."""
    feature = {"type": "Feature", "geometry": geometry,
               "properties": {"name": name, "detail": f"{minutes}-min drive (Mapbox, midday traffic)"}}
    return pdk.Layer("GeoJsonLayer", data={"type": "FeatureCollection", "features": [feature]},
                     get_fill_color=[30, 30, 30, 20], get_line_color=[30, 30, 30, 200],
                     line_width_min_pixels=2, stroked=True, filled=True, id="catchment-polygon")


def catchment_cells_layer(cells: pd.DataFrame, cell_ids: list[str], women: pd.Series) -> pdk.Layer:
    """Catchment cells, darker where more women live."""
    top = max((women[c] for c in cell_ids), default=1) or 1
    rows = [{"polygon": _box(cells, c), "name": f"{cells.at[c, 'name']} ({c})",
             "detail": f"{women[c]:,.0f} women 15+", "color": [0, 121, 107, int(30 + 170 * women[c] / top)]}
            for c in cell_ids]
    return pdk.Layer("PolygonLayer", data=rows, get_polygon="polygon", get_fill_color="color",
                     stroked=False, pickable=True, id="catchment-cells")


AFFLUENCE_LOW, AFFLUENCE_HIGH = [255, 243, 224], [191, 54, 12]   # pale to deep orange, cheap to dear


def affluence_layer(cells: pd.DataFrame) -> pdk.Layer:
    """Cells with an observed median rent (Dubai only), shaded on a log scale; every other cell
    is left uncoloured: no data, weighted neutral."""
    obs = cells[cells.rent_observed.notna()]
    lo, hi = math.log(obs.rent_observed.min()), math.log(obs.rent_observed.max())
    rows = []
    for cid, c in obs.iterrows():
        t = (math.log(c.rent_observed) - lo) / ((hi - lo) or 1)
        rows.append({"polygon": _box(cells, cid), "name": f"{c['name']} ({cid})",
                     "detail": f"Median household rent {c.rent_observed:,.0f} AED/yr (DLD, Jul-Oct 2026)",
                     "color": [round(a + t * (b - a)) for a, b in zip(AFFLUENCE_LOW, AFFLUENCE_HIGH)] + [170]})
    return pdk.Layer("PolygonLayer", data=rows, get_polygon="polygon", get_fill_color="color",
                     stroked=False, pickable=True, id="affluence")


def area_cells_layer(cells: pd.DataFrame, areas: list[Area], decisions: list[AreaDecision],
                     show_skip: bool = False, only: str | None = None) -> pdk.Layer:
    """Growth areas as their grid cells, coloured GROW / WATCH / SKIP. `only`: one area."""
    act = {d.area_id: d.action for d in decisions}
    rows = []
    for a in areas:
        action = act[a.area_id]
        thin = a.women < growth.SKIP_UNDER_WOMEN   # always SKIP: not worth drawing
        if (only and a.area_id != only) or (not only and action == "SKIP" and (not show_skip or thin)):
            continue
        detail = (f"Growth area: {action}<br/>{a.women:,.0f} women 15+ · {a.worker_share:.0%} worker housing"
                  f"<br/>{a.nearest_lounge_km:.1f} km (straight line) to {a.nearest_lounge_id}")
        rows += [{"polygon": _box(cells, c), "area_id": a.area_id, "name": f"{a.name}, {a.emirate}",
                  "action": action, "detail": detail,
                  "color": [*AREA_COLORS[action], 90 if action == "SKIP" else 170]} for c in a.cell_ids]
    return pdk.Layer("PolygonLayer", data=rows, get_polygon="polygon", get_fill_color="color",
                     get_line_color=[255, 255, 255, 120], line_width_min_pixels=0.5, stroked=True,
                     pickable=True, id="areas")


def overlap_layer(cells: pd.DataFrame, reached: dict[str, list[str]], women: pd.Series) -> pdk.Layer:
    """Every open lounge's catchment cells at once (`reached`: cell -> lounges reaching it). Cells
    reached by one lounge are faint teal; shared cells (2+ lounges) are red, deeper with more."""
    rows = [{"polygon": _box(cells, c), "name": f"{cells.at[c, 'name']} ({c})",
             "detail": f"Reached by {len(bs)} lounge(s): {', '.join(sorted(bs))}<br/>{women[c]:,.0f} women 15+",
             "color": [0, 121, 107, 50] if len(bs) == 1 else [211, 47, 47, min(220, 60 + 40 * len(bs))]}
            for c, bs in reached.items()]
    return pdk.Layer("PolygonLayer", data=rows, get_polygon="polygon", get_fill_color="color",
                     stroked=False, pickable=True, id="overlap")


def substitutes_layer(subs: list[dict], layer_id: str = "substitutes") -> pdk.Layer:
    """A lounge's premium substitutes, sized by Google reviews."""
    rows = [{"name": s["name"], "lat": s["lat"], "lng": s["lng"],
             "radius": max(3.0, min(16.0, math.sqrt(s["review_count"]) / 4)),
             "detail": (f"Premium substitute · {s['review_count']:,} reviews · "
                        f"{s['rating'] if s['rating'] is not None else 'no'}★<br/>{s['premium_because']}")}
            for s in subs]
    return pdk.Layer("ScatterplotLayer", data=rows, get_position=["lng", "lat"], get_radius="radius",
                     radius_units=_PIXELS, get_fill_color=[66, 66, 66, 170], get_line_color=[255, 255, 255],
                     stroked=True, line_width_min_pixels=1, pickable=True, id=layer_id)


def view_at(lat: float, lng: float, zoom: float = 11) -> pdk.ViewState:
    return pdk.ViewState(latitude=lat, longitude=lng, zoom=zoom)


def build_deck(layers: list[pdk.Layer], view: pdk.ViewState | None = None) -> pdk.Deck:
    return pdk.Deck(layers=layers, initial_view_state=view or UAE_VIEW, map_style=None,
                    tooltip={"html": "<b>{name}</b><br/>{detail}"})
