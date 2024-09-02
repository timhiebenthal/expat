import pandas as pd
from bs4 import BeautifulSoup
import requests
import re
import dlt
import logging
import yaml
import utils
from tqdm import tqdm


DESTINATION_SCHEMA = "raw_numbeo"
pipeline = utils.define_dlt_pipeline(DESTINATION_SCHEMA)

# configure timestamp for logging
logging.basicConfig(
    format="%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO
)


def get_city_data(city):
    url = f"https://www.numbeo.com/cost-of-living/in/{city}"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    table = soup.find("table", class_="data_wide_table new_bar_table")

    if table is None:
        return None
    else:
        # Extract the data from the table rows
        table_data = []
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if cells:
                category = cells[0].text.strip()
                cost = cells[1].text.strip().replace("\xa0", "")
                table_data.append({"category": category, "cost": cost})

        return [{"city": city, "data": table_data}]


def load_data(data):
    pipeline.run(
        data,
        table_name="cost_of_living",
        write_disposition="replace",
        # write_disposition="merge",
        primary_key="city",
    )
    logging.info(f"Loading successful for {len(data):,d} cities.\n")


def run_pipeline():
    logging.info(f"Executing {__file__} ... \n")
    logging.info("Extracting cost of living data from numbeo.com")

    config = utils.load_config()
    cities = config["cities"]
    data = []
    failed_cities = []
    logging.info(f"Retrieving data for {len(cities):,d} cities.")
    for city in tqdm(cities):
        city_string = city.replace(" ", "-")
        city_data = get_city_data(city_string)
        if city_data:
            data.append(city_data)
        else:
            failed_cities.append(city_string)

    if len(failed_cities) > 0:
        for city in failed_cities:
            logging.error(
                f"ERROR! for '{city}'.Please check & correct this city: 'https://www.numbeo.com/cost-of-living/in/{city}'"
            )

    load_data(data)

    logging.info("Finished loading cost of living data.")


if __name__ == "__main__":
    run_pipeline()
