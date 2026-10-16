"""@bruin
name: raw_numbeo.cost_of_living
connection: duckdb-default

materialization:
  type: table
  strategy: create+replace

tags:
  - layer:ingest
@bruin"""

import logging
import os
from datetime import datetime

import duckdb

from pipeline.lib.numbeo import get_city_data, plan_scrapes


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


def stored_rows():
    """The existing raw_numbeo.cost_of_living rows, or [] when it is not there.

    Tolerant of a table written before ``scraped_at`` existed: those rows come
    back without a timestamp, so they are fetched once rather than reused.
    """
    con = duckdb.connect(os.environ["DUCKDB_LOCATION"], read_only=True)
    try:
        columns = {
            row[0]
            for row in con.execute(
                "select column_name from information_schema.columns "
                "where table_schema = 'raw_numbeo' and table_name = 'cost_of_living'"
            ).fetchall()
        }
        if not columns:
            return []
        scraped = "scraped_at" if "scraped_at" in columns else "null"
        return [
            {
                "city": city,
                "category": category,
                "cost": cost,
                "scraped_at": scraped_at,
            }
            for city, category, cost, scraped_at in con.execute(
                f"select city, category, cost, {scraped} as scraped_at "
                "from raw_numbeo.cost_of_living"
            ).fetchall()
        ]
    finally:
        con.close()


def _scrape(city, slug):
    """Fresh rows for one city, stamped, or None when numbeo has no table."""
    city_data = get_city_data(city, slug=slug)
    if not city_data:
        return None
    scraped_at = datetime.now()
    return [
        {
            "city": city,
            "category": item["category"],
            "cost": item["cost"],
            "scraped_at": scraped_at,
        }
        for item in city_data[0]["data"]
    ]


def materialize():
    """One flat row per city and category, reusing what is already stored.

    dlt used to split this into a parent row per city and a child row per
    category; flattening removes that pair and the model it needed.

    A city is fetched only when it has no stored rows or they are older than the
    TTL, so a re-run with unchanged cities costs no numbeo requests.
    """
    configured = configured_cities()
    stored = stored_rows()
    planned = {city for city, _ in plan_scrapes(configured, stored, datetime.now())}

    rows = []
    for city, slug in configured:
        kept = [row for row in stored if row["city"] == city]
        if city not in planned:
            rows.extend(kept)
            continue

        fetched = _scrape(city, slug)
        if fetched:
            rows.extend(fetched)
        elif kept:
            # numbeo has no table for it right now: keep what we have rather than
            # dropping the city, and leave it stale so the next run retries.
            logging.warning(f"Could not refresh {city}; keeping stored rows.")
            rows.extend(kept)

    if not rows:
        raise RuntimeError(
            "No city returned data - refusing to truncate the cost of living table."
        )
    return rows
