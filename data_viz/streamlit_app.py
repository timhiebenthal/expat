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


location_mapping = {
    "Rent 1 Room in Center": "expense_1_roomappart_center",
    "Rent 1 Room Outside of Center": "expense_1_roomappart_outside",
    "Rent 3 Room in Center": "expense_3_roomappart_center",
    "Rent 3 Room Outside of Center": "expense_3_roomappart_outside",
}

dwh = duckdb.connect(os.environ["DUCKDB_LOCATION"])
df = dwh.sql("select * from dwh.analytics.dataset__cost_earnings_comparison").df()
dwh.close()  # close connection to not block the database

city_list = df["city_name"].sort_values().unique().tolist()
job_list = df["job_title_experience_short"].sort_values().unique().tolist()

with st.expander("Selections") as selection_expander:
    currency = st.selectbox("Select currency:", ["EUR"])
    selected_job = st.selectbox("Enter job title:", job_list)
    selected_cities = st.multiselect(
        "Select cities:", city_list, default=["Berlin", "Munich"]
    )
    selected_location = st.selectbox(
        "Select location preference:", list(location_mapping.keys())
    )

# tabs
main_tab, sandbox_tab = st.tabs(["Home", "Sandbox"])


with main_tab:
    # init DWH connection

    st.markdown(
        "*DISCLAIMER: The values are estimations and are solely for illustrative purposes.*"
    )

    with st.container(border=True) as main_container:
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

    with st.sidebar as config_sidebar:
        st.markdown(
            """
            Add cities or Jobs to the configuration.  
            Run the pipeline afterwards to apply changes.
            """
        )

        cities = utils.editable_df_component(config, "cities")
        jobs = utils.editable_df_component(config, "jobs")

        st.button(
            "Save Changes",
            type="primary",
            on_click=utils.save_config,
            args=(cities, jobs),
            help="Overwrites the configuration file with the current values.",
        )
        st.button(
            "Update Pipeline",
            type="primary",
            on_click=utils.run_pipeline,
            help="Runs the data pipeline to take modifications into account.",
        )


with sandbox_tab:
    # init DWH connection
    dwh = duckdb.connect(os.environ["DUCKDB_LOCATION"])
    cost_df = dwh.sql("select * from dwh.analytics.entity__cost_of_living").df()
    dwh.close()  # close connection to not block the database

    st.dataframe(
        cost_df.pivot_table(
            index=["category_slug", "activity"],
            columns="city_name",
            values="cost_eur",
            aggfunc="mean",
        )[selected_cities].round(2),
        use_container_width=True,
    )
