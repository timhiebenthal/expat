import altair as alt
import streamlit as st
import logging

# configure timestamp for logging
logging.basicConfig(
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)


def create_altair_labelled_vertical_bar_chart(df, x_field, x_label, y_field, y_label):
    """
    creates a vertical bar chart with labels at the end of the bars
    """

    base = alt.Chart(df).encode(
        x=alt.X(
            x_field,
            title=x_label,
            axis=alt.Axis(format="0,.0f", ticks=False, domain=False),
        ),
        y=alt.Y(
            y_field, title=y_label, axis=alt.Axis(labelFontSize=14, titleFontSize=18)
        ),
        text=alt.Text(x_field, format="0,.0f"),
    )

    return base.mark_bar() + base.mark_text(
        align="right", size=18, color="#FFFFFF", dx=-5
    )


def load_config():
    """
    Loads configuration from DuckDB
    Returns:
        type: dict
    """
    import duckdb
    import os

    dwh = duckdb.connect(os.environ["DUCKDB_LOCATION"])
    cities = dwh.table("raw_config.cities").df()["name"].tolist()
    jobs = dwh.table("raw_config.jobs").df().to_dict(orient="records")

    return {
        "cities": cities,
        "jobs": jobs,
    }


def save_config(city_data, jobs_data):
    import yaml
    import time

    config = {
        "cities": city_data["cities"].dropna().tolist(),
        "jobs": jobs_data.dropna().to_dict(orient="records"),
    }

    # saves the dataframe as a yaml file
    with open("config.yml", "w") as file:
        logging.info("Saving to config.yml\n")
        yaml.dump(config, file, sort_keys=False)


def save_config_to_duckdb(city_df, jobs_df):
    import os
    import logging
    import duckdb
    import pandas as pd

    jobs_df = jobs_df.rename(
        columns={
            "Job Title": "job_title",
            "Years of Experience": "years_experience",
        }
    )
    # upload tables to DuckDB
    dwh = duckdb.connect(os.environ["DUCKDB_LOCATION"])
    dwh.sql("CREATE SCHEMA IF NOT EXISTS raw_config")
    dwh.sql("CREATE OR REPLACE TABLE raw_config.cities AS SELECT * FROM city_df")
    dwh.sql("CREATE OR REPLACE TABLE raw_config.jobs AS SELECT * FROM jobs_df")
    logging.info("Tables for jobs and cities uploaded to DuckDB\n")


def editable_df_component(dict, object_name, expander=False):
    import pandas as pd

    if object_name == "cities":
        cols = ["cities"]
    if object_name == "llm_cities":
        cols = ["city", "country", "description"]
    elif object_name == "jobs":
        cols = ["job_title", "years_experience"]
    # else:
    #     raise ValueError(f"Object name '{object_name}' not recognized.")

    df = pd.DataFrame(data=dict[object_name], columns=cols)

    if expander == True:
        expander = st.expander(object_name.title())

        return expander.data_editor(
            data=df,
            num_rows="dynamic",
            hide_index=True,
            # height=750
        )
    else:
        return st.data_editor(
            data=df,
            num_rows="dynamic",
            hide_index=True,
            # height=750
        )


def run_pipeline():
    import subprocess
    import time
    from dbt.cli.main import dbtRunner, dbtRunnerResult

    print("\n>>>> Running pipeline ...\n")

    with st.status("Preparing your comparsion ...", expanded=True) as status:
        st.write("Retrieve earnings data from LLM model ...")
        subprocess.run(["python", "loading/llm_earnings.py"])
        time.sleep(1)

        st.write("Load cities data from config.yml to DuckDB ...")
        subprocess.run(["python", "loading/cities.py"])
        time.sleep(1)

        st.write("Retrieve cost of living data from numbeo.com ...")
        subprocess.run(["python", "loading/costofliving.py"])
        time.sleep(1)

        st.write("Retrieve forex data from Yahoo finance ...")
        subprocess.run(["python", "loading/forex.py"])
        time.sleep(1)

        st.write("Run dbt pipeline ...")
        dbt = dbtRunner()
        cli_args = [
            "run",
            "--target",
            "prod",
            "--profiles-dir",
            "./dbt",
            "--project-dir",
            "./dbt",
        ]
        dbtRunnerResult = dbt.invoke(cli_args)

        if dbtRunnerResult.success:
            print(">>>>>>>>>>>> dbt run successful.")
        else:
            st.error("dbt run failed! Please check the logs.")

        status.update(label="Pipeline complete!", state="complete", expanded=False)
        success_info = st.success("Pipeline run successful! :)", icon="✅")
        time.sleep(2)  # Wait for 2 seconds
        success_info.empty()  # Clear the alert
