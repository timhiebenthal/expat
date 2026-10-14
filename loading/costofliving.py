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


def parse_table_rows(table):
    """Extract category/cost pairs from a numbeo cost-of-living table.

    numbeo pads the table with spacer rows carrying fewer than two cells, so
    cells[1] cannot be indexed unconditionally - doing so raises IndexError and
    aborts the whole loading pipeline on the first city.
    """
    if table is None:
        return []

    rows = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        rows.append(
            {
                "category": cells[0].text.strip(),
                "cost": cells[1].text.strip().replace("\xa0", ""),
            }
        )
    return rows


def build_city_url(city):
    """numbeo keys cities off a slug, so spaces become dashes.

    The slug must stay the bare city name: appending the country ("Munich-Germany")
    is not a valid key and numbeo answers with an error page that carries no table.
    """
    return f"https://www.numbeo.com/cost-of-living/in/{city.replace(' ', '-')}"


def get_city_data(city):
    url = build_city_url(city)
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser")
    table = soup.find("table", class_="data_wide_table new_bar_table")

    table_data = parse_table_rows(table)
    if not table_data:
        # numbeo serves a 200 with an error page ("Cannot find city id for ...")
        # instead of the table, so the page title is the only diagnostic left.
        title = soup.title.text.strip() if soup.title else "no title"
        logging.warning(f"No cost of living table at '{url}' - page says: {title}")
        return None

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
        city_data = get_city_data(city)
        if city_data:
            data.append(city_data)
        else:
            failed_cities.append(city)

    for city in failed_cities:
        logging.error(
            f"ERROR! for '{city}'. Please check & correct this city: '{build_city_url(city)}'"
        )

    if not data:
        logging.error("No city returned data - refusing to truncate the cost of living table.")
        return

    load_data(data)

    logging.info("Finished loading cost of living data.")


if __name__ == "__main__":
    run_pipeline()
