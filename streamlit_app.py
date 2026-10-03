import streamlit as st

from src.webapp.pages import model, product, story

st.set_page_config(page_title="Bedashing Branch Right-Sizing", layout="wide")

pages = [
    st.Page(product.render, title="The Product", icon="🗺️", url_path="product", default=True),
    st.Page(model.render, title="Model, Assumptions & Data", icon="📊", url_path="model"),
    st.Page(story.render, title="Why This Exists", icon="📝", url_path="story"),
]
st.navigation(pages).run()
