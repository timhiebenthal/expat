import streamlit as st
import duckdb
import pandas as pd
import utils


st.subheader("Just a page to test things")

# init DWH connection
dwh = duckdb.connect(utils.DATABASE_LOCATION)
cost_comparsion_df = dwh.sql("select * from dwh.analytics.cost_of_living").df()
dwh.close()  # close connection to not block the database

st.dataframe(
    cost_comparsion_df.pivot_table(
        index=["category_slug", "activity_name"],
        columns="city_name",
        values="cost_eur",
        aggfunc="mean",
    ).round(2),
    use_container_width=True,
)
