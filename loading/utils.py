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
    """
    Loads configuration from DuckDB
    Returns:
        type: dict
    """
    import duckdb
    import os

    dwh = duckdb.connect(os.environ["DUCKDB_LOCATION"])
    cities = dwh.table("raw_config.cities").df()["name"].tolist()
    jobs = dwh.table("raw_config.jobs").df().to_dict(orient="records")

    return {
        "cities": cities,
        "jobs": jobs,
    }


def define_dlt_pipeline(schema_name):
    return dlt.pipeline(
        pipeline_name="dwh",
        destination=dlt.destinations.duckdb(credentials=DATABASE_LOCATION),
        dataset_name=schema_name,
    )
