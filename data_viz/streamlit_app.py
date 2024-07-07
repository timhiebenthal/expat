import streamlit as st
import duckdb
import os
import altair as alt
import utils
import sys
import pandas as pd

config = utils.load_config()


st.set_page_config(page_title="Cost of Living Analysis", layout="wide")
st.title("Cost of Living Analysis")


# init DWH connection
dwh = duckdb.connect(os.environ["DUCKDB_LOCATION"])
df = dwh.sql("select * from dwh.analytics.dataset__cost_earnings_comparison").df()
dwh.close()

city_list = df["city_name"].sort_values().unique().tolist()
job_list = df["job_title_experience_short"].sort_values().unique().tolist()
# x = st.slider("Select a value")
# st.write(x, "squared is", x * x)

location_mapping = {
    "Rent 1 Room in Center": "expense_1_roomappart_center",
    "Rent 1 Room Outside of Center": "expense_1_roomappart_outside",
    "Rent 3 Room in Center": "expense_3_roomappart_center",
    "Rent 3 Room Outside of Center": "expense_3_roomappart_outside",
}

main_tab, config_tab = st.tabs(["Home", "Config"])


# with st.popover("Configurations"):
currency = st.sidebar.selectbox("Select currency:", ["EUR"])
selected_job = st.sidebar.selectbox("Enter job title:", job_list)
selected_cities = st.sidebar.multiselect(
    "Select cities:", city_list, default=["Berlin", "Munich"]
)
selected_location = st.sidebar.selectbox(
    "Select location preference:", list(location_mapping.keys())
)

with main_tab:
    st.markdown(
        "*DISCLAIMER: The values are estimations and are solely for illustrative purposes.*"
    )

    with st.container(border=True):

        selected_df = df.query(
            "city_name.isin(@selected_cities) and job_title_experience_short == @selected_job",
            engine="python",
        ).assign(
            rent_ratio=lambda x: x[location_mapping[selected_location]]
            / x["avg_monthly_net_salary_eur"]
        )

        salary_chart = utils.create_altair_labelled_vertical_bar_chart(
            selected_df,
            "avg_monthly_net_salary_eur",
            "Avg. Net Salary (EUR)",
            "city_name",
            "City",
        )
        rent_chart = utils.create_altair_labelled_vertical_bar_chart(
            selected_df,
            location_mapping[selected_location],
            "Rent (EUR)",
            "city_name",
            "City",
        )

        columns = [
            "city_name",
            "job_title_experience_short",
            "avg_monthly_net_salary_eur",
            location_mapping[selected_location],
            "rent_ratio",
        ]

        st.altair_chart(salary_chart | rent_chart, use_container_width=True)
        st.dataframe(
            data=selected_df[columns],  # .rename(columns=df_column_mapping),
            hide_index=True,
            use_container_width=True,
            column_config={
                "avg_monthly_net_salary_eur": st.column_config.NumberColumn(
                    "Avg. Net Salary (EUR)", format="€ %.0f"
                ),
                location_mapping[selected_location]: st.column_config.NumberColumn(
                    selected_location, format="€ %.0f"
                ),
                "rent_ratio": st.column_config.ProgressColumn(
                    "Rent Ratio", min_value=0, max_value=1, format=" %.02f%%"
                ),
            },
        )


with config_tab:
    st.text(
        "Add cities or Jobs to the configuration file and update the pipeline afterwards to take changes into account."
    )

    with st.container(border=True):
        cities = utils.editable_df_component(config, "cities")
        jobs = utils.editable_df_component(config, "jobs")

    col1, col2, col3, col4 = st.columns(4)
    col1.button(
        "Save Changes",
        type="primary",
        on_click=utils.save_config,
        args=(cities, jobs),
        help="Overwrites the configuration file with the current values.",
    )
    col2.button(
        "Update Pipeline",
        type="primary",
        on_click=utils.run_pipeline,
        help="Runs the data pipeline to take modifications into account.",
    )
