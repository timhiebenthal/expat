import pandas as pd
import dlt
import logging
import json
import os
import yfinance as yf
import utils
import datetime as dt
from tqdm import tqdm
import duckdb

from forex_python.converter import CurrencyRates

DESTINATION_SCHEMA = "raw_forex"
BASE_CURRENCY = "EUR"


# configure timestamp for logging
logging.basicConfig(
    format="%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO
)

# create pipeline config from utils-package
pipeline = utils.define_dlt_pipeline(DESTINATION_SCHEMA)


# get date from yesterday
dt_365daysago = (dt.date.today() - dt.timedelta(days=365)).strftime("%Y-%m-%d")
dt_yesterday = (dt.date.today() - dt.timedelta(days=1)).strftime("%Y-%m-%d")


def get_needed_currencies():
    dwh = duckdb.connect(os.environ["DUCKDB_LOCATION"])
    df = dwh.sql(
        "select distinct currency from dwh.raw_earnings.job_earnings where currency != 'EUR'"
    ).df()

    return df["currency"].unique()


def get_forex_data(base_currency, foreign_currency):
    # get forex data from yahoo finance for last 365 days
    forex_data = yf.download(
        f"{foreign_currency}{base_currency}=X", start=dt_365daysago, end=dt_yesterday
    )
    forex_data = forex_data.reset_index()
    forex_data["from_currency"] = foreign_currency
    forex_data["to_currency"] = base_currency
    logging.info(
        f"Extracted {len(forex_data)} rows for {foreign_currency} into {base_currency}."
    )
    if len(forex_data) == 0:
        return None
    else:
        return forex_data.to_dict(orient="records")


def run_pipeline():
    logging.info(f"Executing {__file__} ... \n")
    logging.info("Retreiving forex data from yahoo finance.")
    data = []

    for foreign_currency in tqdm(get_needed_currencies()):
        forex_data = get_forex_data(BASE_CURRENCY, foreign_currency)
        if forex_data:
            data.append(forex_data)
        pipeline.run(
            data,
            table_name="forex_daily",
            write_disposition="merge",
            primary_key=["Date", "from_currency", "to_currency"],
        )
    logging.info(f"Loading successful.\n {len(data):,d} currencies.")


if __name__ == "__main__":
    run_pipeline()
