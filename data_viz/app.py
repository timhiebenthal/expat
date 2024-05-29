import streamlit as st
from pygwalker.api.streamlit import StreamlitRenderer

import duckdb
import os

dwh = duckdb.connect(os.environ['DUCKDB_LOCATION'])
df = dwh.sql("select * from dwh.analytics.entity__cost_of_living").df()

st.set_page_config(
    page_title="Cost of Living Analysis",
    layout="wide"
)

pyg_app = StreamlitRenderer(df)
pyg_app.explorer()
