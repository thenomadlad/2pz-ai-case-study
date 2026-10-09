"""Small helpers for the notebooks' example cells: pydeck maps on a real street basemap (Carto,
no token) with hover labels."""
import html
import warnings

import pydeck as pdk
from IPython.display import HTML


def show(layers, lat: float, lng: float, zoom: float = 11, height: int = 480) -> HTML:
    deck = pdk.Deck(layers=layers, map_style=pdk.map_styles.CARTO_ROAD, map_provider="carto", tooltip={"text": "{label}"},
                    initial_view_state=pdk.ViewState(latitude=float(lat), longitude=float(lng), zoom=zoom))
    warnings.filterwarnings("ignore", message="Consider using IPython.display.IFrame")
    return HTML(f'<iframe srcdoc="{html.escape(deck.to_html(as_string=True))}" '
                f'style="width:100%;height:{height}px;border:0"></iframe>')


def points(rows: list[dict], color, radius="r", line=(255, 255, 255)) -> pdk.Layer:
    """rows need lat, lng, label; radius is metres, or the name of a field holding metres."""
    return pdk.Layer("ScatterplotLayer", data=[{k: (float(v) if hasattr(v, "item") else v) for k, v in r.items()} for r in rows],
                     get_position="[lng, lat]", get_radius=radius, radius_min_pixels=3,
                     get_fill_color=list(color), get_line_color=list(line), stroked=True,
                     line_width_min_pixels=1, pickable=True)


def shapes(features: list[dict], fill=(42, 120, 214, 40), line=(42, 120, 214)) -> pdk.Layer:
    """GeoJSON features; a `label` property shows on hover. Fill may be a per-feature property name."""
    return pdk.Layer("GeoJsonLayer", data={"type": "FeatureCollection", "features": features},
                     get_fill_color=fill if isinstance(fill, str) else list(fill),
                     get_line_color=list(line), line_width_min_pixels=1.5, pickable=True)
