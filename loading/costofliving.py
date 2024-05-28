import pandas as pd
from bs4 import BeautifulSoup
import requests
import re
import dlt
import logging

# configure timestamp for logging
logging.basicConfig(
    format="%(asctime)s - %(message)s", datefmt="%d-%b-%y %H:%M:%S", level=logging.INFO
)


pipeline = dlt.pipeline(
    pipeline_name="dwh",
    destination=dlt.destinations.duckdb(credentials="database/dwh.duckdb"),
    dataset_name="raw",
)


def get_city_data(city):
    url = f"https://www.numbeo.com/cost-of-living/in/{city}"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    table = soup.find("table", class_="data_wide_table new_bar_table")

    # Extract the data from the table rows
    table_data = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if cells:
            category = cells[0].text.strip()
            cost = cells[1].text.strip()
            table_data.append({"category": category, "cost": cost})

    logging.info(f"Extracted {len(table_data)} rows for City '{city}'")

    return {"city": city, "data": table_data}


def import_data(city):
    data = get_city_data(city)
    load_info = pipeline.run(
        data,
        table_name="players",
        # write_disposition="merge",
        # primary_key="id",
    )
    logging.info("done")


import_data("Munich")
