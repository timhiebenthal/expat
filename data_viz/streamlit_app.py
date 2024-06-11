import streamlit as st

import duckdb
import os

dwh = duckdb.connect(os.environ["DUCKDB_LOCATION"])
df = dwh.sql("select * from dwh.analytics.dataset__cost_earnings_comparison").df()

st.set_page_config(page_title="Cost of Living Analysis", layout="wide")

pyg_app = StreamlitRenderer(df)
pyg_app.explorer()
