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
    "Rent 1 Room in Center": "Housing - 1 Bedroom Apartment",
    "Rent 1 Room Outside of Center": "Housing - 1 Bedroom Apartment Outside Centre",
    "Rent 3 Room in Center": "Housing - 3 Bedrooms Apartment",
    "Rent 3 Room Outside of Center": "Housing - 3 Bedrooms Apartment Outside Centre",
}

# getting data from DWH
dwh = duckdb.connect(os.environ["DUCKDB_LOCATION"])
job_earnings_df = dwh.sql(
    "select * from dwh.analytics.dataset__cost_earnings_comparison"
).df()
activity_df = dwh.sql(
    "select * from dwh.analytics.activity where is_dynamic_in_dashboard is true"
).df()
cost_of_living_df = dwh.sql("select * from dwh.analytics.cost_of_living").df()
dwh.close()  # close connection to not block the database

city_list = job_earnings_df["city_name"].sort_values().unique().tolist()
job_list = job_earnings_df["job_title_experience_short"].sort_values().unique().tolist()

with st.sidebar as selection_sidebar:
    currency = st.selectbox("Select currency:", ["EUR"])
    selected_job = st.multiselect(
        "Enter job title:", job_list, default=job_list[2], max_selections=2
    )
    selected_cities = st.multiselect(
        "Select cities:",
        city_list,
        default=["Berlin", "Munich"],
    )
    selected_location = st.selectbox(
        "Select location preference:", list(location_mapping.keys())
    )

    st.subheader("Define how many times these activities are done in a month:")

    selected_activities = []
    for category in activity_df["activity_category"].sort_values().unique():
        with st.expander(category) as exp:
            activity_dict = activity_df.query("activity_category == @category")[
                ["activity_name", "activity_monthly_default_count"]
            ].to_dict(orient="records")

            for activity in activity_dict:
                activity["selected_count"] = st.number_input(
                    label=activity["activity_name"],
                    value=activity["activity_monthly_default_count"],
                    step=1,
                    min_value=0,
                    max_value=50,
                )
                selected_activities.append(activity)
    # st.json(activity_dict)

# define tabs
main_tab, config_tab = st.tabs(["Home", "Configuration"])

with main_tab:
    # init DWH connection

    st.markdown(
        "*DISCLAIMER: The values are estimations and are solely for illustrative purposes.*"
    )

    with st.container(border=True) as main_container:
        variable_cost_df = cost_of_living_df.query(
            "city_name.isin(@selected_cities)"
        ).merge(pd.DataFrame(selected_activities), on="activity_name", how="inner")
        variable_cost_df["variable_living_cost_eur"] = (
            variable_cost_df["cost_eur"] * variable_cost_df["selected_count"]
        )

        variable_cost_agg = variable_cost_df.groupby("city_name")[
            ["variable_living_cost_eur"]
        ].sum()
        rent_cost_agg = (
            cost_of_living_df[
                cost_of_living_df["activity_name"]
                == location_mapping[selected_location]
            ]
            .query("city_name.isin(@selected_cities)")
            .groupby("city_name")[["cost_eur"]]
            .sum()
            .rename(columns={"cost_eur": "monthly_rent_eur"})
        )
        earnings_agg = (
            job_earnings_df.query(
                "city_name.isin(@selected_cities) and job_title_experience_short == @selected_job",
                engine="python",
            )
            .groupby(["city_name"])
            .agg(
                total_monthly_net_salary_eur=("avg_monthly_net_salary_eur", "sum"),
                jobs=("job_title_experience_short", lambda x: " & ".join(x)),
            )
            .reset_index()
            .set_index("city_name")
        )

        selected_comparsion_df = (
            earnings_agg.join(variable_cost_agg)
            .join(rent_cost_agg)
            .assign(
                rent_ratio=lambda x: x["monthly_rent_eur"]
                / x["total_monthly_net_salary_eur"],
                total_monthly_cost=lambda x: x["variable_living_cost_eur"]
                + x["monthly_rent_eur"],
                spend_earnings_ratio=lambda x: x["total_monthly_cost"]
                / x["total_monthly_net_salary_eur"],
                total_absolute_savings=lambda x: x["total_monthly_net_salary_eur"]
                - x["total_monthly_cost"],
            )
            .reset_index()
        )

        columns = [
            "city_name",
            "jobs",
            "total_monthly_net_salary_eur",
            "monthly_rent_eur",
            "rent_ratio",
            "variable_living_cost_eur",
            "total_monthly_cost",
            "spend_earnings_ratio",
            "total_absolute_savings",
        ]

        st.dataframe(
            data=selected_comparsion_df[
                columns
            ],  # .rename(columns=comparsion_df_column_mapping),
            hide_index=True,
            use_container_width=True,
            column_config={
                "total_monthly_net_salary_eur": st.column_config.NumberColumn(
                    "Household Net Salary (EUR)", format="€ %.0f"
                ),
                "monthly_rent_eur": st.column_config.NumberColumn(
                    selected_location, format="€ %.0f"
                ),
                "rent_ratio": st.column_config.ProgressColumn(
                    "Rent Ratio", min_value=0, max_value=1, format=" %.02f"
                ),
                "total_monthly_cost": st.column_config.NumberColumn(
                    "Total Monthly Cost", format="€ %.0f"
                ),
                "variable_living_cost_eur": st.column_config.NumberColumn(
                    "Additional Cost of Living", format="€ %.0f"
                ),
                "spend_earnings_ratio": st.column_config.ProgressColumn(
                    "Spend/Earnings Ratio", min_value=0, max_value=1, format=" %.02f"
                ),
                "total_absolute_savings": st.column_config.NumberColumn(
                    "Total Absolute Savings", format="€ %.0f"
                ),
            },
        )

with config_tab:
    st.markdown(
        """
        Add cities or Jobs to the configuration.  
        Run the pipeline afterwards to apply changes.
        """
    )

    col1, col2 = st.columns(2)
    with col1:
        cities = utils.editable_df_component(config, "cities")
    with col2:
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

if st.button("Back to Home"):
    st.switch_page("Home.py")
