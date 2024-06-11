import pandas as pd
import dlt
import logging
import json
import yfinance as yf
import utils
import datetime as dt
from tqdm import tqdm


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
    # Load currencies from job_info.json -- should be switched to DuckDB at some point
    with open("raw_data/job_info.json", "r") as file:
        config = json.load(file)

    # Get all foreign currencies from the config file (except EUR)
    foreign_currencies = set(
        [city["currency"] for city in config if city["currency"] != "EUR"]
    )
    return foreign_currencies


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
    return forex_data.to_dict(orient="records")


def load_data():
    data = []
    for foreign_currency in tqdm(get_needed_currencies()):
        data.append(get_forex_data(BASE_CURRENCY, foreign_currency))
        pipeline.run(
            data,
            table_name="forex_daily",
            write_disposition="merge",
            primary_key=["Date", "from_currency", "to_currency"],
        )
    logging.info(f"Loading successful.\n {len(data):,d} currencies.")


if __name__ == "__main__":
    print("__________")
    logging.info(f"Executing {__file__} ... \n")
    logging.info("Retreiving forex data from yahoo finance.")

    load_data()
