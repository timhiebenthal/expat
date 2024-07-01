import os
import json
import yaml
from langchain_core.prompts.few_shot import FewShotPromptTemplate
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
import utils
import logging

# configure timestamp for logging
logging.basicConfig(
    format="%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO
)

DESTINATION_SCHEMA="raw_earnings"
job = "Senior Data Engineer with 7 years of work experience"

fields_of_interest = [
    "city",
    "country",
    "currency",
    "job",
    "average_monthly_gross_salary",
    "net_to_gross_salary_ratio"
]

pipeline = utils.define_dlt_pipeline(DESTINATION_SCHEMA)


def retrieve_city_data(list_of_cities, fields_of_interest, job):

    model = ChatAnthropic(
        model="claude-3-5-sonnet-20240620",
        temperature=0,
        max_tokens=1024,
        timeout=None,
        max_retries=2,
    )

    logging.info("Retrieving data from LLM model ... ")

    prompt_input = f"""Return the specified information for the for the cities of {', '.join(list_of_cities)}.
        The answer should be purely a JSON Array where each city is it's own object with { ', '.join(fields_of_interest)} as keys.
        For the salary consider the average monthly gross salary for a {job} and return only a JSON Object without any other text"""

    response = model.invoke(prompt_input)

    parser = JsonOutputParser()
    prompt = PromptTemplate(
        template=prompt_input,
        input_variables=["city", "job"],
    )

    chain = prompt | model | parser

    response = chain.invoke(
        {
            "job": "Senior Data Engineer with 7 years of work experience",
            "city": "Berlin",
        }
    )

    logging.info(f"Retrieved data of {len(response)} cities.")

    return response


with open("config.yml", "r") as f:
    config = yaml.safe_load(f)

list_of_cities = [city['name'] for city in config["cities"]]
data = retrieve_city_data(list_of_cities, fields_of_interest, job)

pipeline.run(
    data,
    table_name="cost_of_living",
    write_disposition="merge",
    primary_key="city",
)

logging.info(f"LLM data retrieval done.")