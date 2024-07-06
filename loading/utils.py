import dlt
import os
import yaml
import logging

DATABASE_LOCATION = os.environ.get("DUCKDB_LOCATION")

# configure timestamp for logging
logging.basicConfig(
    format="%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO
)


def load_config():
    # loads yaml-config and returns it as a dictionary
    with open("config.yml", "r") as file:
        logging.info("Loading cities from config.yml\n")
        return yaml.safe_load(file)


def define_dlt_pipeline(schema_name):
    return dlt.pipeline(
        pipeline_name="dwh",
        destination=dlt.destinations.duckdb(credentials=DATABASE_LOCATION),
        dataset_name=schema_name,
    )
