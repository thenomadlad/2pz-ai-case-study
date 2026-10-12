"""The app's pages. Pages link to each other through OVERVIEW (the Executive Summary) / PREDICTIONS / LOUNGE / AREA / HOW, which `pages()`
sets, so a link always targets the exact Page object registered with st.navigation."""
import streamlit as st

from src.webapp.pages import area, how, lounge, overview, predictions

OVERVIEW: st.Page | None = None
PREDICTIONS: st.Page | None = None
LOUNGE: st.Page | None = None
AREA: st.Page | None = None
HOW: st.Page | None = None


def pages(default: str = "overview") -> dict[str, list[st.Page]]:
    global OVERVIEW, PREDICTIONS, LOUNGE, AREA, HOW
    OVERVIEW = st.Page(overview.render, title="Executive Summary", icon="📋", url_path="overview",
                       default=default == "overview")
    PREDICTIONS = st.Page(predictions.render, title="What-if explorer", icon="🧪", url_path="explore",
                          default=default == "predictions")
    LOUNGE = st.Page(lounge.render, title="Lounges", icon="💇", url_path="lounge",
                     default=default == "lounge")
    AREA = st.Page(area.render, title="Areas", icon="📍", url_path="area", default=default == "area")
    HOW = st.Page(how.render, title="README", icon="📖", url_path="how",
                  default=default == "how")
    docs = [st.Page(how.doc_page(path), title=title, icon=icon, url_path=url, default=default == url)
            for path, (url, title, icon) in how.DOC_PAGES.items() if url != "how"]
    # a dict gives the sidebar sections; the four docs sit under the README as "Documentation"
    return {"": [OVERVIEW, PREDICTIONS, LOUNGE, AREA], "Documentation": [HOW, *docs]}
