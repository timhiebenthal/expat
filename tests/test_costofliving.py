"""Tests for the numbeo scraper.

numbeo emits spacer rows with fewer than two cells, so indexing cells[1]
unconditionally raises IndexError and takes the whole loading pipeline down.

The logic under test lives in `pipeline/lib/numbeo.py`; `loading/costofliving.py`
stays as the dlt-era caller until cutover.
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
