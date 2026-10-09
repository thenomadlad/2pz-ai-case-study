"""The app's pages. Pages link to each other through OVERVIEW / AREA / BRANCH, which `pages()`
sets, so a link always targets the exact Page object registered with st.navigation."""
import streamlit as st

from src.webapp.pages import area, branch, overview

OVERVIEW: st.Page | None = None
AREA: st.Page | None = None
BRANCH: st.Page | None = None


def pages(default: str = "overview") -> list[st.Page]:
    global OVERVIEW, AREA, BRANCH
    OVERVIEW = st.Page(overview.render, title="Overview", icon="🗺️", url_path="overview",
                       default=default == "overview")
    AREA = st.Page(area.render, title="Areas", icon="📍", url_path="area",
                   default=default == "area")
    BRANCH = st.Page(branch.render, title="Branches", icon="💇", url_path="branch",
                     default=default == "branch")
    return [OVERVIEW, AREA, BRANCH]
