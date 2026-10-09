import streamlit as st

from src.webapp import nav

st.set_page_config(page_title="Bedashing UAE network", layout="wide")
st.navigation(nav.pages()).run()
