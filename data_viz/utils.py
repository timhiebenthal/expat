import altair as alt
import streamlit as st


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
    import logging
    import yaml

    # configure timestamp for logging
    logging.basicConfig(
        format="%(asctime)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
    )
    # loads yaml-config and returns it as a dictionary
    with open("config.yml", "r") as file:
        logging.info("Loading cities from config.yml\n")
        return yaml.safe_load(file)


def save_config(city_data, jobs_data):
    import logging
    import yaml
    import time

    # configure timestamp for logging
    logging.basicConfig(
        format="%(asctime)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
    )

    config = {
        "cities": city_data["cities"].dropna().tolist(),
        "jobs": jobs_data.dropna().to_dict(orient="records"),
    }

    # saves the dataframe as a yaml file
    with open("config.yml", "w") as file:
        logging.info("Saving to config.yml\n")
        yaml.dump(config, file, sort_keys=False)


def editable_df_component(config, object_name):
    import pandas as pd

    if object_name == "cities":
        cols = ["cities"]
    elif object_name == "jobs":
        cols = ["job_title", "years_experience"]
    else:
        raise ValueError(f"Object name '{object_name}' not recognized.")

    df = pd.DataFrame(data=config[object_name], columns=cols)
    expander = st.expander(object_name.title())

    return expander.data_editor(
        data=df,
        num_rows="dynamic",
        hide_index=True,
        # height=750
    )


def run_pipeline():
    import subprocess
    import time
    from dbt.cli.main import dbtRunner, dbtRunnerResult

    print("\n>>>> Run pipeline ...\n")

    with st.status("Running pipeline ...", expanded=True) as status:
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
