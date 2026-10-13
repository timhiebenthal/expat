"""Tests for the numbeo scraper.

numbeo emits spacer rows with fewer than two cells, so indexing cells[1]
unconditionally raises IndexError and takes the whole loading pipeline down.
"""

import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOADING = os.path.join(REPO_ROOT, "loading")

# As served today: header/spacer rows with 0 or 1 cells, then real data rows.
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
def costofliving():
    os.environ.setdefault("DUCKDB_LOCATION", os.path.join(REPO_ROOT, "database/dwh.duckdb"))
    # loading/utils.py and streamlit/utils.py share a module name, so whichever
    # directory comes first on sys.path wins. AppTest leaves streamlit/ there,
    # which would shadow loading/utils.py and break the module-level import.
    sys.path.insert(0, LOADING)
    sys.path.insert(1, REPO_ROOT)
    sys.modules.pop("utils", None)
    sys.modules.pop("costofliving", None)
    import costofliving as module

    return module


def test_short_rows_are_skipped_not_fatal(costofliving):
    from bs4 import BeautifulSoup

    table = BeautifulSoup(NUMBEO_TABLE, "html.parser").find("table")

    rows = costofliving.parse_table_rows(table)

    assert [r["category"] for r in rows] == ["Meal (1)", "Coffee (1)"]
    assert [r["cost"] for r in rows] == ["15.00 €", "3.20 €"]


def test_non_breaking_spaces_are_stripped(costofliving):
    from bs4 import BeautifulSoup

    html = '<table class="data_wide_table new_bar_table">' '<tr><td>Rent</td><td>1\xa0000 €</td></tr>' "</table>"
    table = BeautifulSoup(html, "html.parser").find("table")

    assert costofliving.parse_table_rows(table)[0]["cost"] == "1000 €"


def test_missing_table_yields_no_data(costofliving):
    from bs4 import BeautifulSoup

    assert costofliving.parse_table_rows(BeautifulSoup("<div/>", "html.parser")) == []
