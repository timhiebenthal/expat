"""@bruin
name: raw_numbeo.cost_of_living
connection: duckdb-default

materialization:
  type: table
  strategy: create+replace

tags:
  - layer:ingest
@bruin"""

import os

import duckdb

from pipeline.lib.numbeo import get_city_data


def configured_cities():
    """The cities the app form wrote to raw_config; read, never written here."""
    con = duckdb.connect(os.environ["DUCKDB_LOCATION"], read_only=True)
    try:
        return con.execute("select name from raw_config.cities").df()["name"].tolist()
    finally:
        con.close()


def materialize():
    """One flat row per city and category.

    dlt used to split this into a parent row per city and a child row per
    category; flattening removes that pair and the model it needed.
    """
    rows = []
    for city in configured_cities():
        city_data = get_city_data(city)
        if not city_data:
            continue
        rows.extend(
            {"city": city, "category": item["category"], "cost": item["cost"]}
            for item in city_data[0]["data"]
        )

    if not rows:
        raise RuntimeError(
            "No city returned data - refusing to truncate the cost of living table."
        )
    return rows
