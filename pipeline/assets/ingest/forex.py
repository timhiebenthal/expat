"""@bruin
name: raw_forex.forex_daily
connection: duckdb-default

materialization:
  type: table
  strategy: create+replace

depends:
  - raw_earnings.job_earnings

tags:
  - layer:ingest
@bruin"""

import datetime as dt
import os

import duckdb

from pipeline.lib.forex import BASE_CURRENCY, currency_rates


def configured_currencies():
    """The non-EUR currencies the earnings table actually uses.

    Read from the warehouse, not passed in: every input is a row, not a
    parameter. EUR is excluded because it never needs a rate.
    """
    con = duckdb.connect(os.environ["DUCKDB_LOCATION"], read_only=True)
    try:
        rows = con.execute(
            "select distinct currency from raw_earnings.job_earnings "
            "where currency is not null and currency != 'EUR'"
        ).fetchall()
    finally:
        con.close()
    return sorted(row[0] for row in rows)


def materialize():
    """One flat row per day per currency pair. Returns rows; Bruin writes them."""
    today = dt.date.today()
    start = (today - dt.timedelta(days=365)).strftime("%Y-%m-%d")
    end = (today - dt.timedelta(days=1)).strftime("%Y-%m-%d")

    return currency_rates(
        configured_currencies(), BASE_CURRENCY, start=start, end=end
    )
