"""The Comparison page is the one that reads the warehouse.

test_app_smoke only renders Home.py, so nothing covered the page that actually
joins earnings, cost of living and activity data. It is also the page the user
lands on straight after the pipeline runs, which is why a broken join there went
unnoticed for so long.
"""

import os
import shutil
import sys

import pytest
from streamlit.testing.v1 import AppTest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO_ROOT, "streamlit", "pages", "Comparison.py")
STREAMLIT_DIR = os.path.join(REPO_ROOT, "streamlit")


@pytest.fixture
def warehouse_copy(tmp_path):
    """Comparison.py hardcodes the `dwh` catalog, so the file has to keep its name.

    Copied rather than opened in place: the page reads without closing until the
    script ends and the real warehouse may be open by the running app.
    """
    source = os.path.join(REPO_ROOT, "database", "dwh.duckdb")
    if not os.path.exists(source):
        pytest.skip("no warehouse to copy")

    target = tmp_path / "dwh.duckdb"
    shutil.copyfile(source, target)
    wal = source + ".wal"
    if os.path.exists(wal):
        shutil.copyfile(wal, str(target) + ".wal")
    return target


@pytest.fixture
def comparison_page(warehouse_copy, monkeypatch):
    monkeypatch.setenv("DUCKDB_LOCATION", str(warehouse_copy))

    # streamlit/utils.py freezes DATABASE_LOCATION at import time, and another
    # test module has usually imported it already against the repo's own db.
    sys.path.insert(0, STREAMLIT_DIR)
    saved = sys.modules.pop("utils", None)
    try:
        yield AppTest.from_file(PAGE, default_timeout=60).run()
    finally:
        sys.path.remove(STREAMLIT_DIR)
        sys.modules.pop("utils", None)
        if saved is not None:
            sys.modules["utils"] = saved


def test_page_renders_without_exception(comparison_page):
    assert not comparison_page.exception, "\n".join(
        str(e.value) for e in comparison_page.exception
    )


def test_page_builds_its_city_list_from_the_warehouse(comparison_page):
    pickers = {
        m.label: list(m.options)
        for m in comparison_page.multiselect
        if m.label == "Select cities:"
    }

    assert pickers, "no city picker rendered"
    assert len(pickers["Select cities:"]) > 1


def test_page_offers_every_city_that_has_earnings(comparison_page):
    """A city missing here is a city the join dropped - London's original bug."""
    import duckdb

    picker = next(m for m in comparison_page.multiselect if m.label == "Select cities:")
    offered = set(picker.options)

    dwh = duckdb.connect(os.environ["DUCKDB_LOCATION"], read_only=True)
    try:
        expected = set(
            dwh.sql("select distinct city_name from analytics.job_earnings").df()[
                "city_name"
            ]
        )
    finally:
        dwh.close()

    assert expected, "no earnings in the copy - the fixture proves nothing"
    assert expected == offered
