"""Tests for the numbeo scraper.

numbeo emits spacer rows with fewer than two cells, so indexing cells[1]
unconditionally raises IndexError and takes the whole ingest down.

The logic under test lives in `pipeline/lib/numbeo.py`, which the numbeo ingest
asset calls.
"""

import pytest

NUMBEO_TABLE = """
<table class="data_wide_table new_bar_table">
  <tr><td></td></tr>
  <tr></tr>
  <tr><td>Meal (1)</td><td>15.00 €</td></tr>
  <tr></tr>
  <tr><td>Coffee (1)</td><td>3.20 €</td></tr>
  <tr><td></td></tr>
</table>
"""


@pytest.fixture(scope="module")
def numbeo():
    import pipeline.lib.numbeo as module

    return module


def test_short_rows_are_skipped_not_fatal(numbeo):
    from bs4 import BeautifulSoup

    table = BeautifulSoup(NUMBEO_TABLE, "html.parser").find("table")

    rows = numbeo.parse_table_rows(table)

    assert [r["category"] for r in rows] == ["Meal (1)", "Coffee (1)"]
    assert [r["cost"] for r in rows] == ["15.00 €", "3.20 €"]


def test_non_breaking_spaces_are_stripped(numbeo):
    from bs4 import BeautifulSoup

    html = '<table class="data_wide_table new_bar_table">' '<tr><td>Rent</td><td>1\xa0000 €</td></tr>' "</table>"
    table = BeautifulSoup(html, "html.parser").find("table")

    assert numbeo.parse_table_rows(table)[0]["cost"] == "1000 €"


def test_missing_table_yields_no_data(numbeo):
    from bs4 import BeautifulSoup

    assert numbeo.parse_table_rows(BeautifulSoup("<div/>", "html.parser")) == []


def test_city_slug_replaces_spaces_and_keeps_the_bare_city(numbeo):
    assert (
        numbeo.build_city_url("Mexico City")
        == "https://www.numbeo.com/cost-of-living/in/Mexico-City"
    )
    assert (
        numbeo.build_city_url("Munich-Germany")
        == "https://www.numbeo.com/cost-of-living/in/Munich-Germany"
    )


def test_error_page_without_a_table_is_reported(numbeo, monkeypatch, caplog):
    """numbeo answers an unknown slug with HTTP 200 and an error page.

    That used to look exactly like a city with no data, so the run finished
    with an empty table and no explanation.
    """
    error_page = "<html><head><title>Cannot find city id for Nowhere</title></head></html>"

    class Response:
        content = error_page.encode()
        status_code = 200

        def raise_for_status(self):
            pass

    monkeypatch.setattr(numbeo.requests, "get", lambda *a, **kw: Response())

    with caplog.at_level("WARNING"):
        assert numbeo.get_city_data("Nowhere") is None

    assert "Cannot find city id for Nowhere" in caplog.text


class _JsonResponse:
    """A stand-in for requests' response, exposing only what search_cities uses."""

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _RedirectResponse:
    """A stand-in for the dispatcher's 302, exposing only headers."""

    def __init__(self, location):
        self.headers = {} if location is None else {"Location": location}

    def raise_for_status(self):
        pass


def test_search_cities_returns_the_matches(numbeo):
    """The autocomplete's value is numbeo's city_id, and it stays a string."""
    seen = {}

    def fetch(url, **kwargs):
        seen["url"] = url
        return _JsonResponse([{"label": "Tel Aviv-Yafo, Israel", "value": "6845"}])

    matches = numbeo.search_cities("Tel Aviv", fetch=fetch)

    assert matches == [{"label": "Tel Aviv-Yafo, Israel", "value": "6845"}]
    assert "CitySearchJson" in seen["url"]
    assert "Tel" in seen["url"]


def test_search_cities_returns_empty_when_nothing_matches(numbeo):
    assert (
        numbeo.search_cities("Nowhereville", fetch=lambda *a, **k: _JsonResponse([]))
        == []
    )


def test_canonical_slug_parses_the_malformed_location(numbeo):
    """The dispatcher's Location has no slash: 'https://www.numbeo.com<slug>'."""
    seen = {}

    def fetch(url, **kwargs):
        seen.update(kwargs)
        seen["url"] = url
        return _RedirectResponse("https://www.numbeo.comTel-Aviv-Yafo")

    slug = numbeo.canonical_slug("6845", fetch=fetch)

    assert slug == "Tel-Aviv-Yafo"
    # Redirects must not be followed, or the slug is lost to the followed page.
    assert seen["allow_redirects"] is False
    assert "city_id=6845" in seen["url"]


def test_canonical_slug_returns_none_when_it_cannot_parse(numbeo):
    assert (
        numbeo.canonical_slug(
            "6845", fetch=lambda *a, **k: _RedirectResponse("https://example.com/nope")
        )
        is None
    )
    assert (
        numbeo.canonical_slug("6845", fetch=lambda *a, **k: _RedirectResponse(None))
        is None
    )


LONDONS = [
    {"label": "London, United Kingdom", "value": "1000"},
    {"label": "London, Canada", "value": "2000"},
]


def test_resolve_city_is_unresolved_when_nothing_matches(numbeo):
    result = numbeo.resolve_city(
        "Nowhereville", fetch=lambda *a, **k: _JsonResponse([])
    )

    assert result.state == "unresolved"
    assert result.matches == []


def test_resolve_city_is_resolved_on_a_single_match(numbeo):
    result = numbeo.resolve_city(
        "Munich",
        fetch=lambda *a, **k: _JsonResponse([{"label": "Munich, Germany", "value": "1111"}]),
    )

    assert result.state == "resolved"
    assert result.matches[0]["value"] == "1111"


def test_resolve_city_is_ambiguous_on_several_matches(numbeo):
    result = numbeo.resolve_city(
        "London", fetch=lambda *a, **k: _JsonResponse(LONDONS)
    )

    assert result.state == "ambiguous"
    assert len(result.matches) == 2


def test_resolve_city_narrows_several_matches_by_country(numbeo):
    result = numbeo.resolve_city(
        "London", country="Canada", fetch=lambda *a, **k: _JsonResponse(LONDONS)
    )

    assert result.state == "resolved"
    assert result.matches == [{"label": "London, Canada", "value": "2000"}]


def test_resolve_city_qualifies_the_search_with_the_country(numbeo):
    seen = []

    def fetch(url, **kwargs):
        seen.append(url)
        return _JsonResponse([{"label": "Munich, Germany", "value": "1111"}])

    numbeo.resolve_city("Munich", country="Germany", fetch=fetch)

    assert len(seen) == 1
    assert "Germany" in seen[0]


def test_resolve_city_falls_back_to_the_bare_name_when_the_country_misses(numbeo):
    """An LLM country ("USA") may not match numbeo's naming ("United States")."""
    seen = []

    def fetch(url, **kwargs):
        seen.append(url)
        if "Canada" in url:
            return _JsonResponse([])
        return _JsonResponse([{"label": "Munich, Germany", "value": "1111"}])

    result = numbeo.resolve_city("Munich", country="Canada", fetch=fetch)

    assert result.state == "resolved"
    assert len(seen) == 2
    assert "Canada" in seen[0]


class _TableResponse:
    """A numbeo cost-of-living page carrying the real table."""

    content = NUMBEO_TABLE.encode()

    def raise_for_status(self):
        pass


def test_get_city_data_uses_a_stored_slug(numbeo):
    """A resolved slug drives the URL; the display name only labels the rows."""
    seen = {}

    def fetch(url, **kwargs):
        seen["url"] = url
        return _TableResponse()

    rows = numbeo.get_city_data("Tel Aviv", slug="Tel-Aviv-Yafo", fetch=fetch)

    assert seen["url"] == "https://www.numbeo.com/cost-of-living/in/Tel-Aviv-Yafo"
    # The name stays the identity; only the URL came from the slug.
    assert rows[0]["city"] == "Tel Aviv"


def test_get_city_data_falls_back_to_the_naive_slug_without_one(numbeo):
    seen = {}

    def fetch(url, **kwargs):
        seen["url"] = url
        return _TableResponse()

    numbeo.get_city_data("Mexico City", fetch=fetch)

    assert seen["url"].endswith("/Mexico-City")


def test_get_city_data_flags_access_restricted_distinctly(numbeo, caplog):
    """Throttling and 'no data' look identical on the page; the log must not."""
    page = "<html><head><title>Access Restricted</title></head></html>"

    class Response:
        content = page.encode()

        def raise_for_status(self):
            pass

    with caplog.at_level("WARNING"):
        assert numbeo.get_city_data("Munich", fetch=lambda *a, **k: Response()) is None

    assert "rate-limiting" in caplog.text
