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

config = utils.load_config()
fields_of_interest = [
    "city",
    "country",
    "currency",
    "jobtitle_and_experience",
    "average_monthly_gross_salary",
    "net_to_gross_salary_ratio",
]

pipeline = utils.define_dlt_pipeline(DESTINATION_SCHEMA)


def retrieve_city_data(list_of_cities, fields_of_interest, job):
    model = build_chat_model(temperature=0)

    logging.info(
        f"Retrieving data from LLM model for {len(list_of_cities)} cities ... "
    )

    prompt_input = f"""Return the specified information for the for the cities of {', '.join(list_of_cities)}.
        The answer should be purely a JSON Array where each city is it's own object with { ', '.join(fields_of_interest)} as keys.
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

    data = []
    for job in config["jobs"]:
        logging.info(f"\nRetrieving LLM data for job: {job} ...")
        job_string = f'{job["job_title"]} with {int(job["years_experience"])} years of experience'
        data.append(
            retrieve_city_data(config["cities"], fields_of_interest, job_string)
        )

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
