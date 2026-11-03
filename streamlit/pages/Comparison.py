import streamlit as st
import duckdb
import os
import altair as alt
import utils
import household
import sys
import pandas as pd

config = utils.load_config()

# How many Members the comparison is for, set in the entry mask. It only ever
# decides what the counts open at; the pipeline never sees it.
members = config["members"]

st.set_page_config(page_title="Cost of Living Analysis", layout="wide")
st.title("Cost of Living Analysis")

location_mapping = {
    "Rent 1 Room in Center": "Housing - 1 Bedroom Apartment",
    "Rent 1 Room Outside of Center": "Housing - 1 Bedroom Apartment Outside Centre",
    "Rent 3 Room in Center": "Housing - 3 Bedrooms Apartment",
    "Rent 3 Room Outside of Center": "Housing - 3 Bedrooms Apartment Outside Centre",
}

# getting data from DWH
dwh = duckdb.connect(utils.DATABASE_LOCATION)
job_earnings_df = dwh.sql("select * from dwh.analytics.core__job_earnings").df()
activity_df = dwh.sql(
    "select * from dwh.analytics.core__activity where is_dynamic_in_dashboard is true"
).df()
cost_of_living_df = dwh.sql("select * from dwh.analytics.core__cost_of_living").df()
dwh.close()  # close connection to not block the database


def configured_job_pairs(configured_jobs, available):
    """The jobs the household was configured with, as the sidebar's own strings.

    The pipeline stamps every job as "<title> (<years> years)" and that string is
    what the sidebar offers, so the config rows are matched against it rather than
    the title being reassembled a second way. A household can be configured with
    more jobs than it has earners and the picker allows two, so the list is capped.
    """
    wanted = []
    for job in configured_jobs:
        title = str(job.get("job_title") or "").strip()
        if not title:
            continue
        try:
            years = int(job.get("years_experience"))
        except (TypeError, ValueError):
            continue
        wanted.append(f"{title} ({years} years)")

    matched = [title for title in wanted if title in set(available)]

    return (matched or list(available)[:1])[:2]


if "counted_for" not in activity_df.columns:
    # Failing loudly is right, failing inside pandas is not: this warehouse was
    # built before a Cost item knew whether its count is per Member or shared.
    st.error(
        "This warehouse predates the household counts. Run the pipeline once - "
        "Submit Cities on the home page does it - then reload this page."
    )
    st.stop()

city_list = job_earnings_df["city_name"].sort_values().unique().tolist()
job_list = job_earnings_df["job_title_experience_short"].sort_values().unique().tolist()

with st.sidebar as selection_sidebar:
    currency = st.selectbox("Select currency:", ["EUR"])
    selected_job = st.multiselect(
        "Enter job title:",
        job_list,
        default=configured_job_pairs(config["jobs"], job_list),
        max_selections=2,
    )
    selected_cities = st.multiselect(
        "Select cities:",
        city_list,
        default=city_list,
        # default=["Berlin", "Munich"],
    )
    selected_location = st.selectbox(
        "Select location preference:", list(location_mapping.keys())
    )

    st.subheader("Define how many times these activities are done in a month:")

    # A count belongs to the Household, not to one person: it opens at the seed
    # count for one Member and at twice that for a Per-person Cost item with two.
    # A count the user has changed is theirs and is never rewritten; one they have
    # not touched follows the household the moment it changes, which is what keeps
    # a total from ever sitting at one household size while its labels describe
    # another. Telling those two apart needs the default each count was last
    # derived at, not just the value in the box: a box holding 40 could be an edit
    # or a household that moved.
    if "count_defaults" not in st.session_state:
        st.session_state["count_defaults"] = {}
    derived_defaults = st.session_state["count_defaults"]

    selected_activities = []
    for category in activity_df["activity_category"].sort_values().unique():
        with st.expander(category) as exp:
            activity_dict = activity_df.query("activity_category == @category")[
                ["activity_name", "activity_monthly_default_count", "counted_for"]
            ].to_dict(orient="records")

            for activity in activity_dict:
                name = activity["activity_name"]
                counted_for = activity["counted_for"]
                default = household.default_count(
                    activity["activity_monthly_default_count"], counted_for, members
                )
                widget_key = f"count__{name}"

                previous = derived_defaults.get(name)
                held = (
                    st.session_state[widget_key]
                    if widget_key in st.session_state
                    else None
                )
                if held is None or (held == previous and held != default):
                    # Nothing opened yet, or an untouched count the household has
                    # moved under.
                    st.session_state[widget_key] = default
                derived_defaults[name] = default

                # max_value is generous on purpose: a couple's water opens at 60,
                # and the old ceiling of 50 would refuse its own default.
                selected_count = st.number_input(
                    label=name,
                    step=1,
                    min_value=0,
                    max_value=400,
                    key=widget_key,
                )

                st.caption(
                    household.per_member_figure(selected_count, counted_for, members)
                )
                activity["selected_count"] = selected_count
                selected_activities.append(activity)
    # st.json(activity_dict)

# define tabs
main_tab, config_tab = st.tabs(["Home", "Configuration"])

with main_tab:
    # init DWH connection

    st.markdown(
        """*DISCLAIMER:   
        The values are estimations and are solely for illustrative purposes.*  
        Cities with missing data are excluded from the comparison in this version.
        """
    )

    with st.container(border=True) as main_container:
        other_cost_df = cost_of_living_df.query(
            "city_name.isin(@selected_cities)"
        ).merge(pd.DataFrame(selected_activities), on="activity_name", how="inner")
        other_cost_df["other_monthly_cost_eur"] = (
            other_cost_df["cost_eur"] * other_cost_df["selected_count"]
        )

        other_cost_agg = other_cost_df.groupby("city_name")[
            ["other_monthly_cost_eur"]
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
            earnings_agg.join(other_cost_agg)
            .join(rent_cost_agg)
            .assign(
                rent_ratio=lambda x: x["monthly_rent_eur"]
                / x["total_monthly_net_salary_eur"],
                total_monthly_cost=lambda x: x["other_monthly_cost_eur"]
                + x["monthly_rent_eur"],
                spend_earnings_ratio=lambda x: x["total_monthly_cost"]
                / x["total_monthly_net_salary_eur"],
                total_absolute_savings=lambda x: x["total_monthly_net_salary_eur"]
                - x["total_monthly_cost"],
            )
            .reset_index()
            .query("spend_earnings_ratio.notnull()", engine="python")
        )

        columns = [
            "city_name",
            "jobs",
            "total_monthly_net_salary_eur",
            "monthly_rent_eur",
            "other_monthly_cost_eur",
            "total_monthly_cost",
            "rent_ratio",
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
                "city_name": st.column_config.TextColumn("City"),
                "jobs": st.column_config.TextColumn("Job"),
                "total_monthly_net_salary_eur": st.column_config.NumberColumn(
                    "Household Net Salary (EUR)", format="€ %.0f"
                ),
                "monthly_rent_eur": st.column_config.NumberColumn(
                    selected_location, format="€ %.0f"
                ),
                "other_monthly_cost_eur": st.column_config.NumberColumn(
                    "Other monthly cost", format="€ %.0f"
                ),
                "total_monthly_cost": st.column_config.NumberColumn(
                    "Total Monthly Cost", format="€ %.0f"
                ),
                "rent_ratio": st.column_config.ProgressColumn(
                    "Rent Ratio", min_value=0, max_value=1, format=" %.02f"
                ),
                "spend_earnings_ratio": st.column_config.ProgressColumn(
                    "Spend/Earnings Ratio", min_value=0, max_value=1, format=" %.02f"
                ),
                "total_absolute_savings": st.column_config.NumberColumn(
                    "Total Absolute Savings", format="€ %.0f"
                ),
            },
        )

        highest_ratio_city = selected_comparsion_df[
            selected_comparsion_df["spend_earnings_ratio"]
            == selected_comparsion_df["spend_earnings_ratio"].min()
        ].head(1)

        highest_absolute_city = selected_comparsion_df[
            selected_comparsion_df["total_absolute_savings"]
            == selected_comparsion_df["total_absolute_savings"].max()
        ].head(1)

        st.divider()
        st.markdown("### Results:")
        st.markdown(
            f"**{highest_ratio_city['city_name'].values[0]}** has the best Spend to Earnings Ratio of **{highest_ratio_city['spend_earnings_ratio'].values[0]:.0%}**.  \n"
            + f"**{highest_absolute_city['city_name'].values[0]}** has the highest absolute savings of **{highest_absolute_city['total_absolute_savings'].values[0]:,.2f} €**."
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
        cities = utils.editable_df_component(dict=config, object_name="cities")
    with col2:
        jobs = utils.editable_df_component(dict=config, object_name="jobs")

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
