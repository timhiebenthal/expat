import altair as alt
import logging
import os
import subprocess
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Docker and Cloud Run inject DUCKDB_LOCATION as a real environment variable. On
# the host there is no shell export, so read it from .env. load_dotenv leaves an
# already-set variable alone, so the container's value always wins.
REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")


def define_database_location():
    """Resolve DUCKDB_LOCATION once.

    A relative path is anchored at the repo root so the app does not depend on
    the working directory. Docker and Cloud Run pass an absolute path, which is
    used as-is.
    """
    location = Path(os.environ.get("DUCKDB_LOCATION", "database/dwh.duckdb"))
    resolved = str(location if location.is_absolute() else REPO_ROOT / location)
    # dbt reads DUCKDB_LOCATION through env_var() and resolves a relative path
    # against its own working directory, and the loaders run as subprocesses,
    # so normalise it to an absolute path once, here.
    os.environ["DUCKDB_LOCATION"] = resolved
    return resolved


DATABASE_LOCATION = define_database_location()

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

    # DuckDB allows a single writer per file, so the connection has to be
    # released before anything else - the loaders and dbt - can open it. The app
    # is long-lived, so leaving this to garbage collection keeps the write lock
    # for as long as the process lives.
    dwh = duckdb.connect(DATABASE_LOCATION)
    try:
        cities = dwh.table("raw_config.cities").df()["name"].tolist()
        jobs = dwh.table("raw_config.jobs").df().to_dict(orient="records")
    finally:
        dwh.close()

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
    dwh = duckdb.connect(DATABASE_LOCATION)
    try:
        dwh.sql("CREATE SCHEMA IF NOT EXISTS raw_config")
        dwh.sql("CREATE OR REPLACE TABLE raw_config.cities AS SELECT * FROM city_df")
        dwh.sql("CREATE OR REPLACE TABLE raw_config.jobs AS SELECT * FROM jobs_df")
        logging.info("Tables for jobs and cities uploaded to DuckDB\n")
    finally:
        # Released here on purpose: run_pipeline() is called straight after this
        # and its loaders are separate processes that need the write lock.
        dwh.close()


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


def dbt_executable():
    """The dbt that belongs to this interpreter's virtualenv."""
    candidate = Path(sys.executable).with_name("dbt")
    return str(candidate) if candidate.exists() else "dbt"


def run_dbt(args):
    """Run dbt in its own process, and return whether it succeeded.

    Deliberately not dbtRunner().invoke(): dbt-duckdb keeps its DuckDB handle
    open for the life of the process it runs in, and closing the runner does not
    release it - the handle survives even del + gc.collect(). Streamlit is
    long-lived, so an in-process run pins the write lock on the warehouse and
    everything after it dies with

        IOException: Could not set lock on file ... Conflicting lock is held in
        ... (PID <the streamlit process>)

    A subprocess takes the lock and drops it when it exits.
    """
    dbt_dir = str(REPO_ROOT / "dbt")
    command = [
        dbt_executable(),
        *args,
        "--profiles-dir",
        dbt_dir,
        "--project-dir",
        dbt_dir,
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    print(result.stdout)
    print(result.stderr)
    return result.returncode == 0


def run_pipeline():
    import time

    print("\n>>>> Running pipeline ...\n")

    # Paths are derived from the repo root, never hardcoded: the same code runs
    # from the host (make streamlit_app) and from /app inside the container.
    loaders = [
        ("Retrieve earnings data from LLM model ...", "llm_earnings.py"),
        ("Retrieve cost of living data from numbeo.com ...", "costofliving.py"),
        ("Retrieve forex data from Yahoo finance ...", "forex.py"),
    ]

    with st.status("Preparing your comparsion ...", expanded=True) as status:
        for label, script in loaders:
            st.write(label)
            # sys.executable rather than "python": the app already runs inside
            # the project venv, and that is the interpreter with the loaders'
            # dependencies on its path.
            result = subprocess.run(
                [sys.executable, str(REPO_ROOT / "loading" / script)],
                capture_output=True,
                text=True,
            )
            print(result.stdout)
            print(result.stderr)
            if result.returncode != 0:
                # A failing loader used to be swallowed, so the run carried on
                # and reported success while nothing had been loaded.
                st.error(f"{script} failed with exit code {result.returncode}.")
                status.update(label="Pipeline failed", state="error", expanded=True)
                return False
            time.sleep(1)

        st.write("Run dbt pipeline ...")
        if not run_dbt(["deps"]):
            st.error("dbt deps failed! Please check the logs.")
            status.update(label="Pipeline failed", state="error", expanded=True)
            return False
        print(">>>>>>>>>>>> dbt deps installed.")

        if run_dbt(["build", "--target", "prod"]):
            print(">>>>>>>>>>>> dbt run successful.")

            status.update(label="Pipeline complete!", state="complete", expanded=False)
            success_info = st.success("Pipeline run successful! :)", icon="✅")
            time.sleep(2)  # Wait for 2 seconds
            success_info.empty()  # Clear the alert
            return True
        else:
            st.error("dbt run failed! Please check the logs.")
            status.update(label="Pipeline failed", state="error", expanded=True)
            return False
