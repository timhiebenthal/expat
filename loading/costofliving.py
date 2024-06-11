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
        raise ValueError(f"No data found for City '{city}'. Please check {url}")
    else:
        # Extract the data from the table rows
        table_data = []
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if cells:
                category = cells[0].text.strip()
                cost = cells[1].text.strip().replace("\xa0", "")
                table_data.append({"category": category, "cost": cost})

        # logging.info(f"Extracted info for City '{city}'")

    return [{"city": city, "data": table_data}]


def load_data(data):
    pipeline.run(
        data,
        table_name="cost_of_living",
        write_disposition="merge",
        primary_key="city",
    )
    logging.info(f"Loading successful for {len(data):,d} cities.\n")


if __name__ == "__main__":
    print("__________")
    logging.info(f"Executing {__file__} ... \n")
    logging.info("Extracting cost of living data from numbeo.com")

    with open("config.yml", "r") as f:
        config = yaml.safe_load(f)

    data = []

    for city in tqdm(config["cities"]):
        city_string = city.replace(" ", "-")
        data.append(get_city_data(city_string))

    load_data(data)
