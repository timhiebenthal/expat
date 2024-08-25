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
job_earnings_df = dwh.sql("select * from dwh.analytics.dataset__cost_earnings_comparison").df()
activity_df = dwh.sql("select * from dwh.analytics.activity where is_dynamic_in_dashboard is true").df()
cost_of_living_df = dwh.sql("select * from dwh.analytics.cost_of_living").df()
dwh.close()  # close connection to not block the database

city_list = job_earnings_df["city_name"].sort_values().unique().tolist()
job_list = job_earnings_df["job_title_experience_short"].sort_values().unique().tolist()

with st.sidebar as selection_sidebar:
    currency = st.selectbox("Select currency:", ["EUR"])
    selected_job = st.multiselect("Enter job title:", job_list, default=job_list[2], max_selections=2)
    selected_cities = st.multiselect(
        "Select cities:", city_list, default=["Berlin", "Munich"], 
    )
    selected_location = st.selectbox(
        "Select location preference:", list(location_mapping.keys())
    )

    st.subheader("Define how many times these activities are done in a month:")
    
    selected_activities = []
    for category in activity_df['activity_category'].unique():
        with st.expander(category) as exp:
            activity_dict = activity_df.query("activity_category == @category")[['activity_name', 'activity_monthly_default_count']].to_dict(orient='records')

            for activity in activity_dict:
                activity['selected_count'] = st.number_input(
                    label=activity['activity_name'], 
                    value=activity['activity_monthly_default_count'], 
                    step=1,
                    min_value=0,
                    max_value=50
                    )
                selected_activities.append(activity)
    # st.json(activity_dict)

# tabs
main_tab, sandbox_tab = st.tabs(["Home", "Sandbox"])


with main_tab:
    # init DWH connection

    st.markdown(
        "*DISCLAIMER: The values are estimations and are solely for illustrative purposes.*"
    )

    with st.container(border=True) as main_container:
        variable_cost_df = (cost_of_living_df
            .query("city_name.isin(@selected_cities)")
            .merge(pd.DataFrame(selected_activities), on='activity_name', how='inner')
            )
        variable_cost_df['variable_living_cost_eur'] = variable_cost_df['cost_eur'] * variable_cost_df['selected_count']
        
        variable_cost_agg = (variable_cost_df
                .groupby("city_name")[["variable_living_cost_eur"]].sum()
        )
        rent_cost_agg = (cost_of_living_df[cost_of_living_df['activity_name'] == selected_location]
                .groupby("city_name")[["cost_eur"]].sum()
                .rename(columns={"cost_eur": "monthly_rent_eur"})
        )
        earnings_agg = (job_earnings_df
                .query(
                    "city_name.isin(@selected_cities) and job_title_experience_short == @selected_job",
                    engine="python")
                # sum up 'avg_monthly_net_salary_eur'  and also aggregate the strings of 'job_title_experience_short with " & " as delimiter
                .groupby(["city_name"]).agg(
                    avg_monthly_net_salary_eur=("avg_monthly_net_salary_eur", "sum"),
                    jobs=("job_title_experience_short", lambda x: " & ".join(x))
                )
                .reset_index()
                .set_index("city_name")
        )
        st.dataframe(earnings_agg)
        st.dataframe(rent_cost_agg)
        st.dataframe(variable_cost_agg)
        selected_comparsion_df = earnings_agg.join(variable_cost_agg).join(rent_cost_agg).assign(
            rent_ratio=lambda x: x["monthly_rent_eur"] / x["avg_monthly_net_salary_eur"],
            total_monthly_cost=lambda x: x["variable_living_cost_eur"] + x["monthly_rent_eur"],
            spend_earnings_ratio=lambda x: x["total_monthly_cost"] / x["avg_monthly_net_salary_eur"]
        )


        columns = [
            "city_name",
            "jobs",
            "avg_monthly_net_salary_eur",
            "monthly_rent_eur",
            "rent_ratio",
            "total_monthly_cost",
            "variable_living_cost_eur",
            "spend_earnings_ratio"
        ]

        st.dataframe(
            data=selected_comparsion_df[columns],  # .rename(columns=comparsion_df_column_mapping),
            hide_index=True,
            use_container_width=True,
            column_config={
                "avg_monthly_net_salary_eur": st.column_config.NumberColumn(
                    "Avg. Net Salary (EUR)", format="€ %.0f"
                ),
                "monthly_rent_eur": st.column_config.NumberColumn(
                    selected_location, format="€ %.0f"
                ),
                "rent_ratio": st.column_config.ProgressColumn(
                    "Rent Ratio", min_value=0, max_value=1, format=" %.02f%%"
                ),
                "total_monthly_cost": st.column_config.NumberColumn(
                    "Total Monthly Cost", format="€ %.0f"
                ),
                "variable_living_cost_eur": st.column_config.NumberColumn(
                    "Variable Living Cost", format="€ %.0f"
                ),
                "spend_earnings_ratio": st.column_config.ProgressColumn(
                    "Spend/Earnings Ratio", min_value=0, max_value=1, format=" %.02f%%"
                ),
            },
        )

    # with st.sidebar as config_sidebar:
    #     st.markdown(
    #         """
    #         Add cities or Jobs to the configuration.  
    #         Run the pipeline afterwards to apply changes.
    #         """
    #     )

    #     cities = utils.editable_df_component(config, "cities")
    #     jobs = utils.editable_df_component(config, "jobs")

    #     st.button(
    #         "Save Changes",
    #         type="primary",
    #         on_click=utils.save_config,
    #         args=(cities, jobs),
    #         help="Overwrites the configuration file with the current values.",
    #     )
    #     st.button(
    #         "Update Pipeline",
    #         type="primary",
    #         on_click=utils.run_pipeline,
    #         help="Runs the data pipeline to take modifications into account.",
    #     )


with sandbox_tab:
    # init DWH connection
    dwh = duckdb.connect(os.environ["DUCKDB_LOCATION"])
    cost_comparsion_df = dwh.sql("select * from dwh.analytics.cost_of_living").df()
    dwh.close()  # close connection to not block the database

    st.dataframe(
        cost_comparsion_df.pivot_table(
            index=["category_slug", "activity_name"],
            columns="city_name",
            values="cost_eur",
            aggfunc="mean",
        )[selected_cities].round(2),
        use_container_width=True,
    )
