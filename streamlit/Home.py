import streamlit as st
import duckdb
import os
import altair as alt
import utils
import sys
from langchain_core.prompts import PromptTemplate
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
import pandas as pd
import logging

# configure timestamp for logging
logging.basicConfig(
    format="%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO
)
config = utils.load_config()

# home_page = st.Page("Home.py", icon="🌍")
# comparison_page = st.Page("Comparison.py", icon="📈")
# st.navigation([home_page, comparison_page], position="hidden")


st.title("Welcome to the Expat Planning App!")
st.markdown(
    "Let's find the best city for you to live in! Please provide some information to tailor the results to your preferences."
)

if "city_suggestions" not in st.session_state:
    st.session_state.city_suggestions = None

if "jobs_df" not in st.session_state:
    st.session_state.jobs_df = pd.DataFrame(
        {"Job Title": ["Data Engineer"], "Years of Experience": [7]}
    )


def retrieve_city_suggestions(form_dict):
    max_output_tokens = 1800
    model = ChatAnthropic(
        model="claude-3-5-sonnet-20240620",
        temperature=0.2,
        max_tokens=max_output_tokens,
        timeout=None,
        max_retries=2,
    )

    logging.info(f"Retrieving suggestions on cities to live in from LLM model ... ")

    # prompt_input = find_cities(form_dict)

    parser = JsonOutputParser()
    prompt = PromptTemplate.from_template(
        """
        Please help me out finding a new city to live in.
        I'm currently living in {current_city} and are looking for a new place to live in.
        I really enjoyed visiting the cities {fav_cities}.
        Other information which is important to me is: {criteria}

        Please list my current and favourite cities and up to 8 cities which fit my criteria.
        The response should be purely a JSON Array, where each city is it's own object fitting these descriptions.
        """
    )

    chain = prompt | model | parser

    response = chain.invoke(
        {
            "current_city": form_dict["current_city"],
            "fav_cities": ", ".join(form_dict["fav_cities"]),
            "criteria": form_dict["criteria"],
        }
    )

    logging.info(f"Retrieved data of {len(response)} cities.")

    return response


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

    st.markdown(
        "Please provide some Job titles and years of experience which are relevant for this benchmark"
    )

    jobs_df_editable = st.data_editor(
        data=st.session_state.jobs_df,
        num_rows="dynamic",
        hide_index=True,
    )

    submitted = st.form_submit_button("Find Cities")

    if submitted:
        form_data = {
            "current_city": current_city,
            "fav_cities": [x.strip() for x in fav_cities.split(",") if x],
            "criteria": criteria,
            "jobs": jobs_df_editable,
        }

        with st.status("Asking Claude for suggestions ...") as status:
            st.session_state.city_suggestions = retrieve_city_suggestions(form_data)
            st.session_state.jobs_df = jobs_df_editable
            st.divider()

if st.session_state.city_suggestions:
    st.text("Here are some cities you might enjoy living in:")
    st.text(
        "Feel free to add cities on your own behalf or remove cities you are not interested in.\nOnly the 'name' column is required."
    )
    city_df_editable = st.data_editor(
        data=pd.DataFrame(st.session_state.city_suggestions),
        num_rows="dynamic",
        hide_index=True,
    )
    st.session_state.city_suggestions = city_df_editable.to_dict("records")

# Button outside the form
if st.button("Submit Cities", disabled=st.session_state.city_suggestions is None):
    if st.session_state.city_suggestions:
        utils.save_config_to_duckdb(
            city_df=pd.DataFrame(st.session_state.city_suggestions),
            jobs_df=st.session_state.jobs_df,
        )
        st.success("Data saved successfully!")
        # We don't reset city_suggestions here to allow for editing and resubmission
    else:
        st.error("Please find cities first before submitting.")

    ## debugging
    import os

    print("Current working directory:", os.getcwd())
    print("Files in current working directory:", os.listdir())
    # print("Files in /page directory:", os.listdir("pages"))

    # TO DO: save cities and jobs to config.yml and run pipeline
    utils.run_pipeline()

    print("Current working directory:", os.getcwd())
    print("Files in current working directory:", os.listdir())
    # print("Files in /page directory:", os.listdir("pages"))

    st.switch_page(f"/app/streamlit/pages/Comparison.py")
