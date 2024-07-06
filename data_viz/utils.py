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
            axis=alt.Axis(format="0,.0f", ticks=False, domain=False)
            ),
        y=alt.Y(y_field, title=y_label, axis=alt.Axis(labelFontSize=14, titleFontSize=18)),
        text=alt.Text(x_field, format="0,.0f"),
    )

    return (
        base.mark_bar()
        + base.mark_text(align='right', size=18, color='#FFFFFF', dx=-5)
        )


def load_config():
    import logging
    import yaml
    # configure timestamp for logging
    logging.basicConfig(
        format="%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO
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
        format="%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO
    )
    
    config = {
        "cities": city_data['cities'].dropna().tolist(),
        "jobs": jobs_data['jobs'].dropna().tolist()
    }

    # saves the dataframe as a yaml file
    with open("config.yml", "w") as file:
        logging.info("Saving to config.yml\n")
        yaml.dump(config, file)
    
    success_info = st.success("Config saved! :)", icon="✅")
    time.sleep(2) # Wait for 3 seconds
    success_info.empty() # Clear the alert


def editable_df_component(config, object_name):
    import pandas as pd

    city_df = pd.DataFrame(data=config[object_name], columns=[object_name])
    exp_cities = st.expander(object_name.title())

    return exp_cities.data_editor(
        data=city_df,
        num_rows="dynamic", 
        hide_index=True,
        # height=750
        )
    



def run_pipeline():
    print("dummy run")