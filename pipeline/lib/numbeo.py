"""numbeo cost-of-living scraping, free of network calls at import.

The HTTP fetch is resolved at call time, so tests never touch the network and a
caller can inject its own fetcher. Called by `pipeline/assets/ingest/numbeo.py`.
"""

import logging
from datetime import datetime, timedelta
from typing import NamedTuple
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
CITY_URL_BASE = "https://www.numbeo.com/cost-of-living/in"

# numbeo enforces a monthly page-view quota and blocks the IP once it is gone, so
# a stored city is reused until it is this old rather than re-fetched every run.
# Prices do not move fast enough to justify the quota cost.
SCRAPE_TTL_DAYS = 180


class NumbeoThrottled(RuntimeError):
    """numbeo is rate-limiting us instead of answering."""


# numbeo signals a throttle two ways: a 429/403, or a 200 HTML "Access Restricted"
# page. raise_for_status() turns the first into an opaque HTTPError, so the check
# has to run before it.
THROTTLE_STATUS = {403, 429}


def _is_throttled(response):
    """True when numbeo answered with its rate-limit page rather than data.

    That page is a 200, so the status code says nothing and the body is the signal.
    """
    content = getattr(response, "content", b"") or b""
    if isinstance(content, str):
        content = content.encode()
    return b"access restricted" in content.lower()


def _raise_if_throttled(response, url):
    """Raise NumbeoThrottled before raise_for_status can mask it as an HTTPError."""
    if getattr(response, "status_code", 200) in THROTTLE_STATUS or _is_throttled(
        response
    ):
        raise NumbeoThrottled(f"numbeo is rate-limiting us at '{url}'")


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
    return f"{CITY_URL_BASE}/{city.replace(' ', '-')}"


def search_cities(term, fetch=None):
    """Ask numbeo's autocomplete which cities match ``term``.

    Returns the raw ``[{"label": ..., "value": ...}]`` list, where ``value`` is
    numbeo's city_id, or ``[]`` when nothing matches.
    """
    fetch = fetch or requests.get
    url = f"{CITY_SEARCH_URL}?term={quote_plus(term)}"
    response = fetch(url, timeout=REQUEST_TIMEOUT)
    _raise_if_throttled(response, url)
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
    _raise_if_throttled(response, url)
    response.raise_for_status()

    location = response.headers.get("Location", "")
    if not location.startswith(NUMBEO_HOST):
        return None
    slug = location[len(NUMBEO_HOST):].strip("/").split("/")[-1]
    return slug or None


class Resolution(NamedTuple):
    """The outcome of matching a display name to numbeo cities.

    ``state`` is "resolved" (exactly one), "ambiguous" (several - the app asks),
    or "unresolved" (none). ``matches`` are numbeo's own ``{label, value}`` dicts.
    """

    state: str
    matches: list


def resolve_city(name, country=None, fetch=None):
    """Match a display name to numbeo's cities, narrowing by country.

    The country is only a hint: numbeo's naming may differ from the caller's
    ("USA" vs "United States"), so a qualified search that finds nothing is
    retried with the bare name.
    """
    matches = search_cities(f"{name}, {country}" if country else name, fetch=fetch)
    if not matches and country:
        matches = search_cities(name, fetch=fetch)

    if not matches:
        return Resolution("unresolved", [])
    if len(matches) == 1:
        return Resolution("resolved", matches)

    if country:
        narrowed = [m for m in matches if country.lower() in m["label"].lower()]
        if len(narrowed) == 1:
            return Resolution("resolved", narrowed)

    return Resolution("ambiguous", matches)


def _scraped_at(value):
    """A stored ``scraped_at`` as a datetime; ISO strings are accepted too."""
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def plan_scrapes(configured, stored, now, ttl_days=SCRAPE_TTL_DAYS):
    """The ``(name, slug)`` pairs that need a fetch, in ``configured`` order.

    ``stored`` is the existing ``raw_numbeo.cost_of_living`` rows. A city is
    reused while its newest ``scraped_at`` is within the TTL; one with no rows at
    all, or rows older than that, is fetched. A table written before the column
    existed has no timestamps, so everything is fetched once.
    """
    newest = {}
    for row in stored:
        city = row.get("city")
        when = _scraped_at(row.get("scraped_at"))
        if city and when and (city not in newest or when > newest[city]):
            newest[city] = when

    cutoff = now - timedelta(days=ttl_days)
    return [
        (name, slug)
        for name, slug in configured
        if newest.get(name) is None or newest[name] < cutoff
    ]


def get_city_data(city, slug=None, fetch=None):
    """Return ``[{"city": ..., "data": [...]}]``, or None when numbeo has no table.

    ``slug`` is numbeo's canonical key for the city, resolved at the app boundary
    and stored on the config row; when present it drives the URL and the display
    name is only carried through. Without one the naive slug is used, which is
    right for most cities but not all (Tel Aviv -> Tel-Aviv-Yafo).

    ``fetch`` defaults to ``requests.get`` and is resolved at call time, which is
    what lets a test monkeypatch it.
    """
    fetch = fetch or requests.get
    url = f"{CITY_URL_BASE}/{slug}" if slug else build_city_url(city)
    response = fetch(url, timeout=REQUEST_TIMEOUT)
    _raise_if_throttled(response, url)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser")
    table = soup.find("table", class_=TABLE_CLASS)

    table_data = parse_table_rows(table)
    if not table_data:
        # numbeo serves a 200 with an error page ("Cannot find city id for ...")
        # instead of the table, so the page title is the only diagnostic left.
        # Throttling was already caught above, so this is a genuinely missing city.
        title = soup.title.text.strip() if soup.title else "no title"
        logging.warning(f"No cost of living table at '{url}' - page says: {title}")
        return None

    return [{"city": city, "data": table_data}]
