import dlt
import logging
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Docker and Cloud Run inject DUCKDB_LOCATION as a real environment variable. On
# the host there is no shell export, so read it from .env. load_dotenv leaves an
# already-set variable alone, so the container's value always wins.
REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")


def define_database_location():
    """Resolve DUCKDB_LOCATION once.

    A relative path is anchored at the repo root so the loaders do not depend on
    the working directory. Docker and Cloud Run pass an absolute path, which is
    used as-is.
    """
    location = Path(os.environ.get("DUCKDB_LOCATION", "database/dwh.duckdb"))
    resolved = str(location if location.is_absolute() else REPO_ROOT / location)
    # Normalise once so every consumer - dlt, dbt via env_var(), and the script
    # that reads os.environ directly - agrees on the same absolute path.
    os.environ["DUCKDB_LOCATION"] = resolved
    return resolved


DATABASE_LOCATION = define_database_location()

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

    # Closed before returning: dlt opens its own connection to the same file a
    # moment later, and DuckDB takes a single writer per database file.
    dwh = duckdb.connect(DATABASE_LOCATION)
    try:
        cities = dwh.table("raw_config.cities").df()["name"].tolist()
        jobs = dwh.table("raw_config.jobs").df().to_dict(orient="records")
    finally:
        dwh.close()

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
