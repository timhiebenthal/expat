"""The Comparison page is the one that reads the warehouse.

test_app_smoke only renders Home.py, so nothing covered the page that actually
joins earnings, cost of living and activity data. It is also the page the user
lands on straight after the pipeline runs, which is why a broken join there went
unnoticed for so long.
"""

import os
import shutil
import subprocess
import sys

import pytest
from streamlit.testing.v1 import AppTest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO_ROOT, "streamlit", "pages", "Comparison.py")
STREAMLIT_DIR = os.path.join(REPO_ROOT, "streamlit")


def bruin_cli():
    """The CLI from PATH, or from ~/.local/bin where the installer puts it."""
    found = shutil.which("bruin")
    if found:
        return found
    candidate = os.path.join(os.path.expanduser("~"), ".local", "bin", "bruin")
    return candidate if os.path.exists(candidate) else None


@pytest.fixture(scope="module")
def prepared_warehouse(tmp_path_factory):
    """The app's warehouse, brought up to the shape the page reads.

    The page reads what the transform layer produces, and the app's own warehouse
    is only as current as the last time the app ran the pipeline - so the copy is
    transformed once, here, rather than the page failing on a column the app's
    warehouse has not been rebuilt with yet. The app's file is never written to.
    """
    source = os.path.join(REPO_ROOT, "database", "dwh.duckdb")
    if not os.path.exists(source):
        pytest.skip("no warehouse to copy")

    cli = bruin_cli()
    if cli is None:
        pytest.skip("the bruin CLI is not installed")

    target = tmp_path_factory.mktemp("warehouse") / "dwh.duckdb"
    shutil.copyfile(source, target)
    wal = source + ".wal"
    if os.path.exists(wal):
        shutil.copyfile(wal, str(target) + ".wal")

    result = subprocess.run(
        [
            cli,
            "run",
            "pipeline",
            "--selector",
            "tag:layer:transform",
            "--workers",
            "1",
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "DUCKDB_LOCATION": str(target)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    return target


@pytest.fixture
def warehouse_copy(prepared_warehouse, tmp_path):
    """A per-test copy of it, so one test's settings cannot reach another's."""
    target = tmp_path / "dwh.duckdb"
    shutil.copyfile(prepared_warehouse, target)
    return target


def write_settings(warehouse, members):
    """Put a Member count where the entry mask puts one."""
    import duckdb

    dwh = duckdb.connect(str(warehouse))
    try:
        dwh.sql("create schema if not exists raw_config")
        dwh.sql(
            "create or replace table raw_config.settings as "
            f"select 'members' as key, '{members}' as value"
        )
    finally:
        dwh.close()


@pytest.fixture
def render_page(monkeypatch):
    """Render Comparison.py against a warehouse copy.

    streamlit/utils.py freezes DATABASE_LOCATION at import time, and another test
    module has usually imported it already against the repo's own db, so `utils`
    stays out of sys.modules for the length of the test - a rerun has to re-import
    it to pick the copy up.
    """
    sys.path.insert(0, STREAMLIT_DIR)
    saved = sys.modules.pop("utils", None)

    def render(warehouse, members=None):
        if members is not None:
            write_settings(warehouse, members)
        monkeypatch.setenv("DUCKDB_LOCATION", str(warehouse))
        return AppTest.from_file(PAGE, default_timeout=60).run()

    yield render

    sys.path.remove(STREAMLIT_DIR)
    sys.modules.pop("utils", None)
    if saved is not None:
        sys.modules["utils"] = saved


@pytest.fixture
def comparison_page(warehouse_copy, render_page):
    return render_page(warehouse_copy)


def counts(page):
    """The rendered monthly count per Cost item, by the label the sidebar shows."""
    return {element.label: element.value for element in page.number_input}


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
            dwh.sql("select distinct city_name from analytics.core__job_earnings").df()[
                "city_name"
            ]
        )
    finally:
        dwh.close()

    assert expected, "no earnings in the copy - the fixture proves nothing"
    assert expected == offered


def test_counts_open_at_one_member_without_settings(comparison_page):
    """A warehouse from before the entry mask had a household: today's numbers."""
    values = counts(comparison_page)

    assert values["Groceries - 1.5l Water"] == 30
    assert values["Restaurant - Cappuccino"] == 4
    assert values["Utilities - Internet 60Mbps"] == 1


def test_counts_open_at_the_households_size(warehouse_copy, render_page):
    """The couple's opening counts, and the shared ones that must not move."""
    page = render_page(warehouse_copy, members=2)

    assert not page.exception, "\n".join(str(e.value) for e in page.exception)

    values = counts(page)
    assert values["Restaurant - Cappuccino"] == 8
    assert values["Groceries - 1.5l Water"] == 60
    assert values["Utilities - Mobile Phone Plan"] == 2
    assert values["Utilities - Internet 60Mbps"] == 1
    assert values["Utilities - Basic for 85m2 Apartment"] == 1
    assert values["Restaurant - Mid-range Meal for 2"] == 4


def test_each_count_is_keyed_by_its_cost_item(comparison_page):
    """The key is what lets an edited count be told apart from a derived one."""
    keys = {element.key for element in comparison_page.number_input}

    assert "count__Groceries - 1.5l Water" in keys


def test_a_count_reads_as_its_per_member_share(warehouse_copy, render_page):
    page = render_page(warehouse_copy, members=2)
    captions = [caption.value for caption in page.caption]

    assert "4 per Member" in captions, captions
    assert "30 per Member" in captions, captions
    assert "shared - paid once for the household" in captions, captions


def test_an_edited_count_survives_a_household_change(warehouse_copy, render_page):
    """Untouched counts follow the household; the number you set stays yours."""
    page = render_page(warehouse_copy, members=2)

    values = counts(page)
    assert values["Restaurant - Cappuccino"] == 8, "the couple's default is missing"
    assert values["Groceries - 1.5l Water"] == 60, "the couple's default is missing"

    {element.label: element for element in page.number_input}[
        "Restaurant - Cappuccino"
    ].set_value(40).run()

    assert counts(page)["Restaurant - Cappuccino"] == 40

    write_settings(warehouse_copy, 1)
    page.run()

    values = counts(page)
    assert values["Restaurant - Cappuccino"] == 40, "an edit was overwritten"
    assert values["Groceries - 1.5l Water"] == 30, "an untouched count did not follow"
