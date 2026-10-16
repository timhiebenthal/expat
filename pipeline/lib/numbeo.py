"""numbeo cost-of-living scraping, free of network calls at import.

The HTTP fetch is resolved at call time, so tests never touch the network and a
caller can inject its own fetcher. Called by `pipeline/assets/ingest/numbeo.py`.
"""

import logging
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

TABLE_CLASS = "data_wide_table new_bar_table"
REQUEST_TIMEOUT = 30

# numbeo's own autocomplete and its city dispatcher. Both are internal - the site
# uses them itself - but they are the only source of the canonical slug, which is
# not derivable from the display name (Tel Aviv -> Tel-Aviv-Yafo).
CITY_SEARCH_URL = "https://www.numbeo.com/common/CitySearchJson"
DISPATCHER_URL = "https://www.numbeo.com/common/dispatcher.jsp"
NUMBEO_HOST = "https://www.numbeo.com"


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


def search_cities(term, fetch=None):
    """Ask numbeo's autocomplete which cities match ``term``.

    Returns the raw ``[{"label": ..., "value": ...}]`` list, where ``value`` is
    numbeo's city_id, or ``[]`` when nothing matches.
    """
    fetch = fetch or requests.get
    url = f"{CITY_SEARCH_URL}?term={quote_plus(term)}"
    response = fetch(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def canonical_slug(city_id, fetch=None):
    """The slug numbeo keys ``city_id`` under, or None if it cannot be read.

    The dispatcher answers with a 302 whose Location is malformed - the slug is
    appended to the host with no slash, e.g.
    ``https://www.numbeo.comTel-Aviv-Yafo``. The slug is still canonical, so it
    is parsed out defensively rather than treated as a URL.
    """
    fetch = fetch or requests.get
    url = f"{DISPATCHER_URL}?city_id={city_id}"
    response = fetch(url, timeout=REQUEST_TIMEOUT, allow_redirects=False)
    response.raise_for_status()

    location = response.headers.get("Location", "")
    if not location.startswith(NUMBEO_HOST):
        return None
    slug = location[len(NUMBEO_HOST):].strip("/").split("/")[-1]
    return slug or None


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
