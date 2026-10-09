import streamlit as st

from src.webapp import nav

st.set_page_config(page_title="Bedashing Network Right-Sizing", layout="wide")
st.navigation(nav.pages()).run()
