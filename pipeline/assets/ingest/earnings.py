"""@bruin
name: raw_earnings.job_earnings
connection: duckdb-default

materialization:
  type: table
  strategy: create+replace

tags:
  - layer:ingest
@bruin"""

import os

import duckdb

from pipeline.lib.earnings import (
    assert_every_city_came_back,
    attach_job_string,
    build_job_string,
    retrieve_city_earnings,
)


def _read(query):
    """raw_config is app-owned, so it is read, never written here."""
    con = duckdb.connect(os.environ["DUCKDB_LOCATION"], read_only=True)
    try:
        return con.execute(query).df()
    finally:
        con.close()


def configured_cities():
    return _read("select name from raw_config.cities")["name"].tolist()


def configured_jobs():
    return _read(
        "select job_title, years_experience from raw_config.jobs"
    ).to_dict(orient="records")


def _llm_invoke(prompt):
    """The one place a live model is reached; injectable so the logic stays testable."""
    from llm_client import CityEarningsList, build_chat_model

    chain = build_chat_model(temperature=0).with_structured_output(CityEarningsList)
    return [city.model_dump() for city in chain.invoke(prompt).cities]


def materialize():
    """One row per city per configured job, with the canonical job string."""
    cities = configured_cities()
    rows = []
    for job in configured_jobs():
        job_string = build_job_string(job["job_title"], job["years_experience"])
        returned = retrieve_city_earnings(cities, job_string, _llm_invoke)
        assert_every_city_came_back(returned, cities)
        rows.extend(
            attach_job_string(returned, job["job_title"], job["years_experience"])
        )
    return rows
