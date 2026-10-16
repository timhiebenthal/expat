import streamlit as st
import duckdb
import os
import altair as alt
import utils
import sys
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llm_client import build_chat_model, CitySuggestionList

import pandas as pd
import logging
import time

# configure timestamp for logging
logging.basicConfig(
    format="%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO
)
# config = utils.load_config()

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

# Set on Submit; holds the annotated resolution while the panel is on screen.
if "resolution" not in st.session_state:
    st.session_state.resolution = None


def retrieve_city_suggestions(form_dict):
    model = build_chat_model(temperature=0.2)

    logging.info(f"Retrieving suggestions on cities to live in from LLM model ... ")

    # prompt_input = find_cities(form_dict)

    prompt = PromptTemplate.from_template(
        """
        Please help me out finding a new city to live in.
        I'm currently living in {current_city} and are looking for a new place to live in.
        I really enjoyed visiting the cities {fav_cities}.
        Other information which is important to me is: {criteria}

        Please list my current and favourite cities and up to 8 cities which fit my criteria.
        The response should be a JSON Array where each city is an object with the keys
        "name", "country" and "description".
        """
    )

    chain = prompt | model.with_structured_output(CitySuggestionList)

    response = chain.invoke(
        {
            "current_city": form_dict["current_city"],
            "fav_cities": ", ".join(form_dict["fav_cities"]),
            "criteria": form_dict["criteria"],
        }
    )

    cities = [city.model_dump() for city in response.cities]

    logging.info(f"Retrieved data of {len(cities)} cities.")

    return cities


def _save_and_run(picks, annotated):
    """Write the resolved rows, then run the pipeline - the happy path."""
    rows = utils.apply_resolution(annotated, picks)
    utils.save_config_to_duckdb(
        city_df=pd.DataFrame(rows), jobs_df=st.session_state.jobs_df
    )
    save_success = st.success("Data saved successfully!")
    time.sleep(1)
    save_success.empty()
    # city_suggestions is not reset, so the user can edit and resubmit.

    if utils.run_pipeline():
        st.switch_page("pages/Comparison.py")
    else:
        st.error("Something went wrong. Please check the logs for more information.")


def _render_resolution_panel(annotated):
    """The HITL surface: same page as the editor, its own widgets.

    All the decision logic lives in ``utils``; this only renders and gathers
    choices, which is what keeps it testable without driving the UI.
    """
    st.subheader("Resolution")
    st.caption(
        "Each city is matched to Numbeo's own listing. Anything that did not "
        "match cleanly needs a quick decision below. Nothing is saved until you "
        "confirm."
    )

    resolved = [c for c in annotated if c["state"] == "resolved"]
    ambiguous = [c for c in annotated if c["state"] == "ambiguous"]
    unresolved = [c for c in annotated if c["state"] == "unresolved"]

    if resolved:
        pairs = "\n".join(
            f"- {c['name']} -> {c['matches'][0]['label']}" for c in resolved
        )
        st.success(f"Resolved:\n\n{pairs}")

    choices = {}
    if ambiguous:
        st.warning(
            f"{len(ambiguous)} name(s) match more than one place - pick the one you mean."
        )
        for city in ambiguous:
            labels = [m["label"] for m in city["matches"]]
            picked = st.radio(
                f"Which **{city['name']}**?", labels, index=0, key=f"amb-{city['name']}"
            )
            choices[city["name"]] = {
                "city_id": next(
                    m["value"] for m in city["matches"] if m["label"] == picked
                )
            }

    if unresolved:
        st.warning(
            f"Numbeo has no match for {len(unresolved)} name(s) - rename, paste a "
            "slug, or remove."
        )
        for city in unresolved:
            with st.expander(f"**{city['name']}** - no Numbeo match", expanded=True):
                c1, c2, c3 = st.columns([2, 2, 1])
                new_name = c1.text_input(
                    "Rename", value=city["name"], key=f"ren-{city['name']}"
                )
                manual = c2.text_input(
                    "or paste a Numbeo slug", key=f"slug-{city['name']}"
                )
                drop = c3.checkbox("Remove", key=f"drop-{city['name']}")
                choices[city["name"]] = {
                    "rename": new_name,
                    "manual": manual,
                    "drop": drop,
                }

    # A rename is a new name to resolve, so it is resolved now and the panel
    # re-renders to say whether the city is still blocked.
    renames = {
        name: choice["rename"].strip()
        for name, choice in choices.items()
        if choice.get("rename") and choice["rename"].strip() != name
    }
    if renames:
        try:
            st.session_state.resolution = utils.rename_rows(annotated, renames)
        except utils.ResolutionThrottled:
            st.error(
                "Numbeo is rate-limiting us right now (Access Restricted). Retry in "
                "a few minutes."
            )
        else:
            st.rerun()

    blocked = bool(ambiguous or unresolved)
    if st.button("Confirm and run pipeline", disabled=blocked, key="confirm"):
        try:
            picks = utils.picks_from(annotated, choices)
        except utils.ResolutionThrottled:
            st.error(
                "Numbeo is rate-limiting us right now (Access Restricted). Nothing "
                "was saved - retry in a few minutes."
            )
        else:
            _save_and_run(picks, annotated)
    if blocked:
        st.caption(
            "Confirm is disabled until every city is resolved. Nothing is written."
        )


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

        with st.status("Asking the model for suggestions ...") as status:
            st.session_state.city_suggestions = retrieve_city_suggestions(form_data)
            st.session_state.jobs_df = jobs_df_editable
            st.divider()

if st.session_state.city_suggestions:
    st.text("Here are some cities you might enjoy living in:")
    st.text(
        "Feel free to add/remove cities on your own behalf.\nOnly the 'name' column is required."
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
        try:
            annotated = utils.resolve_city_rows(st.session_state.city_suggestions)
        except utils.ResolutionThrottled:
            annotated = None
            st.error(
                "Numbeo is rate-limiting us right now (Access Restricted). Nothing "
                "was saved - your previous city list is unchanged. Retry in a few "
                "minutes, or paste slugs manually."
            )
        if annotated:
            st.session_state.resolution = annotated
            # The happy path is unchanged: everything resolved means no panel.
            if all(city["state"] == "resolved" for city in annotated):
                _save_and_run(utils.picks_from(annotated), annotated)
    else:
        st.error("Please find cities first before submitting.")

# The panel only appears when something still needs the user's call.
resolution = st.session_state.get("resolution")
if resolution and any(city["state"] != "resolved" for city in resolution):
    _render_resolution_panel(resolution)
