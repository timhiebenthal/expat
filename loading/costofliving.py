import pandas as pd
from bs4 import BeautifulSoup
import requests
import re
import dlt
import logging
import yaml
import utils

# configure timestamp for logging
logging.basicConfig(
    format="%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO
)

DESTINATION_SCHEMA="raw_numbeo"
pipeline = utils.define_dlt_pipeline(DESTINATION_SCHEMA)

logging.info(">>>>>>>>>>>>>>>>> Extracting cost of living data from numbeo.com\n")


def get_city_data(city):
    url = f"https://www.numbeo.com/cost-of-living/in/{city}"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    table = soup.find("table", class_="data_wide_table new_bar_table")

    if table is None:
        raise ValueError(f"No data found for City '{city}'. Please check {url}")
    else:
        # Extract the data from the table rows
        table_data = []
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if cells:
                category = cells[0].text.strip()
                cost = cells[1].text.strip().replace('\xa0', '')
                table_data.append({"category": category, "cost": cost})

        logging.info(f"Extracted {len(table_data)} rows for City '{city}'")

    return [{"city": city, "data": table_data}]


def load_data(city):
    city_string = city.replace(" ", "-")
    data = get_city_data(city_string)

    pipeline.run(
        data,
        table_name="cost_of_living",
        write_disposition="merge",
        primary_key="city",
    )
    logging.info("Loading successful.\n")


with open("config.yml", "r") as f:
    config = yaml.safe_load(f)

for city in config["cities"]:
    load_data(city["name"])
