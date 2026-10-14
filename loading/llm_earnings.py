import os
import json
import sys
import yaml
from langchain_core.prompts.few_shot import FewShotPromptTemplate
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llm_client import build_chat_model, CityEarningsList

import utils
import logging

# configure timestamp for logging
logging.basicConfig(
    format="%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO
)

DESTINATION_SCHEMA = "raw_earnings"

fields_of_interest = [
    "city",
    "country",
    "currency",
    "jobtitle_and_experience",
    "average_monthly_gross_salary",
    "net_to_gross_salary_ratio",
]

pipeline = utils.define_dlt_pipeline(DESTINATION_SCHEMA)


def build_job_string(job_title, years_experience):
    """The canonical job string, in the shape prep__job_earnings parses.

    Built here instead of taken from the model. prep__job_earnings parses the
    title back out and inner-joins it against clean__config_jobs, so a reworded
    title - "Analytics Engineer" coming back as "Staff Analytics Engineer", as
    the real data did - drops every row for that job with no error at all.
    """
    return f"{job_title} with {int(years_experience)} years of experience"


def attach_job_string(cities, job_title, years_experience):
    """Stamp every record with the job string, overriding whatever came back.

    The prompt asks the model to echo the title verbatim, but that is only
    advisory: it is the same model, on the same endpoint, that reworded it
    before. This is the guarantee.
    """
    job_string = build_job_string(job_title, years_experience)
    return [{**city, "jobtitle_and_experience": job_string} for city in cities]


def assert_every_city_came_back(cities, requested):
    """Fail loudly when the model drops or invents a city.

    city_name is what prep__numbeo_cost_of_living joins on, so a missing city
    disappears from the dashboard exactly the way London did.
    """
    returned = {city["city"].strip().lower() for city in cities}
    missing = [city for city in requested if city.strip().lower() not in returned]

    if missing:
        raise RuntimeError(
            f"No earnings returned for {', '.join(missing)}. "
            "Refusing to write a partial earnings table."
        )


def retrieve_city_data(list_of_cities, fields_of_interest, job):
    model = build_chat_model(temperature=0)

    logging.info(
        f"Retrieving data from LLM model for {len(list_of_cities)} cities ... "
    )

    prompt_input = f"""Return the specified information for the for the cities of {', '.join(list_of_cities)}.
        The answer should be purely a JSON Array where each city is it's own object with { ', '.join(fields_of_interest)} as keys.
        Use the city names exactly as they are spelled above, and use the job title exactly as it appears in "{job}" - do not
        shorten it, expand it, or add a seniority word such as "Staff" or "Senior" that was not given to you.
        For the salary consider the average monthly gross salary for a {job} and return only a JSON Object without any other text"""

    prompt = PromptTemplate(template=prompt_input)

    # Structured output rather than JsonOutputParser: DeepSeek wraps JSON in
    # markdown fences, which the parser can't read. This also guarantees the
    # keys match what the job_earnings primary key expects.
    chain = prompt | model.with_structured_output(CityEarningsList)

    response = chain.invoke(
        {
            "job": job,
        }
    )

    cities = response.cities
    logging.info(f"Retrieved data of {len(cities)} cities.")

    return [city.model_dump() for city in cities]


def run_pipeline():
    logging.info(f"Executing {__file__} ... \n")

    config = utils.load_config()
    data = []
    for job in config["jobs"]:
        logging.info(f"\nRetrieving LLM data for job: {job} ...")
        job_string = build_job_string(job["job_title"], job["years_experience"])
        cities = retrieve_city_data(config["cities"], fields_of_interest, job_string)
        assert_every_city_came_back(cities, config["cities"])
        data.append(attach_job_string(cities, job["job_title"], job["years_experience"]))

    pipeline.run(
        data,
        table_name="job_earnings",
        write_disposition="replace",
        # write_disposition="merge",
        primary_key=["city", "jobtitle_and_experience"],
    )

    logging.info(f"LLM data retrieval done.")


if __name__ == "__main__":
    run_pipeline()
