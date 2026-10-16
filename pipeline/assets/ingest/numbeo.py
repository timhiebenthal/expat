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
    """The cities the app wrote, as ``(name, slug)`` pairs.

    numbeo_slug is added by the app's resolution step. A table written before it
    existed (or by hand) has no such column, so it is detected rather than
    assumed, and the slug comes back as None.
    """
    con = duckdb.connect(os.environ["DUCKDB_LOCATION"], read_only=True)
    try:
        columns = {
            row[0]
            for row in con.execute(
                "select column_name from information_schema.columns "
                "where table_schema = 'raw_config' and table_name = 'cities'"
            ).fetchall()
        }
        slug = "numbeo_slug" if "numbeo_slug" in columns else "null"
        return con.execute(
            f"select name, {slug} as numbeo_slug from raw_config.cities"
        ).fetchall()
    finally:
        con.close()


def materialize():
    """One flat row per city and category.

    dlt used to split this into a parent row per city and a child row per
    category; flattening removes that pair and the model it needed.
    """
    rows = []
    for city, slug in configured_cities():
        city_data = get_city_data(city, slug=slug)
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
