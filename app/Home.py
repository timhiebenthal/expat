import streamlit as st
import duckdb
import os
import altair as alt
import utils
import sys
import pandas as pd

config = utils.load_config()

# home_page = st.Page("Home.py", icon="🌍")
# comparison_page = st.Page("Comparison.py", icon="📈")
# st.navigation([home_page, comparison_page], position="hidden")


st.title("Welcome to the Expat Planning App!")
st.markdown(
    "Let's find the best city for you to live in! Please provide some information to tailor the results to your preferences."
)


def find_cities(form_dict):
    print("TO DO: run form input through LLM and return 8 cities which are a good fit")
    prompt_text = f"""
    Please help me out finding a new city to live in.
    I'm currently living in {form_dict['current_city']} and are looking for a new place to live in.
    I really enjoyed visiting the cities {', '.join(form_dict['fav_cities'])}.
    Other information which is important to me is: {form_dict['criteria']}

    Please return an array of up to 8 cities which fit these descriptions.
    """


with st.form("inputs") as form_inputs:
    current_city = st.text_input(
        label="Where do you live currently?", placeholder="Berlin, Germany"
    )
    fav_cities = st.text_area(
        label="Name up to 5 cities you really enjoyed being to.",
        placeholder="London, New York, Barcelona...",
    )

    criteria = st.text_area(
        label="Describe the attributes which are important to you.",
        placeholder="I want to live in a vibrant city with good public transportation and warm/hot weather.\nFeeling safe at night is also important to me.",
    )

    form_data = {
        "current_city": current_city,
        "fav_cities": [x.strip() for x in fav_cities.split(",") if x],
        "criteria": criteria,
    }

    submitted = st.form_submit_button("Submit")

    if submitted:
        find_cities(form_data)


if st.button("Compare"):
    st.switch_page("pages/Comparison.py")


st.json(form_data)
