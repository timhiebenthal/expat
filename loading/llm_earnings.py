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
    max_output_tokens = 1800
    model = ChatAnthropic(
        model="claude-3-5-sonnet-20240620",
        temperature=0,
        max_tokens=max_output_tokens,
        timeout=None,
        max_retries=2,
    )

    logging.info(
        f"Retrieving data from LLM model for {len(list_of_cities)} cities ... "
    )

    prompt_input = f"""Return the specified information for the for the cities of {', '.join(list_of_cities)}.
        The answer should be purely a JSON Array where each city is it's own object with { ', '.join(fields_of_interest)} as keys.
        For the salary consider the average monthly gross salary for a {job} and return only a JSON Object without any other text"""

    # response = model.invoke(prompt_input)

    # # if response.response_metadata['output_tokens'] == max_output_tokens:
    # #     raise Exception("Output token limit reached. Please increase the max_output_tokens parameter or iterate")
    # print(response.content)

    parser = JsonOutputParser()
    prompt = PromptTemplate(template=prompt_input)

    chain = prompt | model | parser

    response = chain.invoke(
        {
            "job": job,
        }
    )

    logging.info(f"Retrieved data of {len(response)} cities.")

    return response


def run_pipeline():
    logging.info(f"Executing {__file__} ... \n")
    for job in config["jobs"]:
        logging.info(f"\nRetrieving LLM data for job: {job} ...")
        job_string = f'{job["job_title"]} with {int(job["years_experience"])} years of experience'
        data = retrieve_city_data(config["cities"], fields_of_interest, job_string)

        pipeline.run(
            data,
            table_name="job_earnings",
            write_disposition="merge",
            primary_key=["city", "jobtitle_and_experience"],
        )

    logging.info(f"LLM data retrieval done.")


if __name__ == "__main__":
    run_pipeline()
