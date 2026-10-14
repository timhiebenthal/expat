"""numbeo cost-of-living scraping, free of dlt and of network calls at import.

The HTTP fetch is resolved at call time, so tests never touch the network and a
caller can inject its own fetcher. `loading/costofliving.py` stays as the
dlt-era entry point until cutover and is not imported from here.
"""

import logging

import requests
from bs4 import BeautifulSoup

TABLE_CLASS = "data_wide_table new_bar_table"
REQUEST_TIMEOUT = 30


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


def get_city_data(city, fetch=None):
    """Return ``[{"city": ..., "data": [...]}]``, or None when numbeo has no table.

    ``fetch`` defaults to ``requests.get`` and is resolved at call time, which is
    what lets a test monkeypatch it.
    """
    fetch = fetch or requests.get
    url = build_city_url(city)
    response = fetch(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser")
    table = soup.find("table", class_=TABLE_CLASS)

    table_data = parse_table_rows(table)
    if not table_data:
        # numbeo serves a 200 with an error page ("Cannot find city id for ...")
        # instead of the table, so the page title is the only diagnostic left.
        title = soup.title.text.strip() if soup.title else "no title"
        logging.warning(f"No cost of living table at '{url}' - page says: {title}")
        return None

    return [{"city": city, "data": table_data}]
