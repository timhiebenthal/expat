import pandas as pd
import dlt
import logging
import yaml
import yfinance as yf
import utils
import datetime as dt

# configure timestamp for logging
logging.basicConfig(
    format="%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO
)

DESTINATION_SCHEMA = "raw_forex"
BASE_CURRENCY = "EUR"

# create pipeline config from utils-package
pipeline = utils.define_dlt_pipeline(DESTINATION_SCHEMA)


#get date from yesterday
dt_365daysago = (dt.date.today() - dt.timedelta(days=365)).strftime("%Y-%m-%d")
dt_yesterday = (dt.date.today() - dt.timedelta(days=1)).strftime("%Y-%m-%d")


def get_needed_currencies():
    # Load currencies from config.yml
    with open('config.yml', 'r') as file:
        config = yaml.safe_load(file)

    # Get all foreign currencies from the config file (except EUR)
    foreign_currencies = set([city['currency'] for city in config['cities'] if city['currency'] != 'EUR'])
    return foreign_currencies


def get_forex_data(base_currency, foreign_currency):
    # get forex data from yahoo finance for last 365 days
    forex_data = yf.download(f"{foreign_currency}{base_currency}=X", start=dt_365daysago, end=dt_yesterday)
    forex_data = forex_data.reset_index()
    forex_data["from_currency"] = foreign_currency
    forex_data["to_currency"] = base_currency
    logging.info(f"Extracted {len(forex_data)} rows for {foreign_currency} into {base_currency}.")
    return forex_data.to_dict(orient="records")


def load_data():
    for foreign_currency in get_needed_currencies():
        data = get_forex_data(BASE_CURRENCY, foreign_currency)
        pipeline.run(
            data,
            table_name="forex_daily",
            write_disposition="merge",
            primary_key=["Date", "from_currency", "to_currency"],
        )
        logging.info(f"Loading successful for {foreign_currency}.\n")


load_data()