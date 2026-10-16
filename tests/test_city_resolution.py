"""The app-side resolution helpers in `streamlit/utils.py`.

They are deliberately free of Streamlit widgets, so the resolution decision can
be tested without driving the UI - which `AppTest` cannot do for a `data_editor`.
"""

import sys
from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
STREAMLIT_DIR = REPO_ROOT / "streamlit"


@pytest.fixture(scope="module")
def utils():
    sys.path.insert(0, str(STREAMLIT_DIR))
    try:
        import utils as module

        yield module
    finally:
        sys.path.remove(str(STREAMLIT_DIR))


def _scratch_cities(tmp_path, *, with_slug):
    db = tmp_path / "scratch.duckdb"
    con = duckdb.connect(str(db))
    con.execute("create schema raw_config")
    if with_slug:
        con.execute(
            "create table raw_config.cities "
            "(name varchar, country varchar, description varchar, "
            "numbeo_slug varchar, numbeo_city_id varchar)"
        )
        con.execute(
            "insert into raw_config.cities values "
            "('Tel Aviv', 'Israel', 'warm', 'Tel-Aviv-Yafo', '6845')"
        )
    else:
        con.execute(
            "create table raw_config.cities "
            "(name varchar, country varchar, description varchar)"
        )
        con.execute(
            "insert into raw_config.cities values ('Munich', 'Germany', 'home')"
        )
    con.close()
    return str(db)


def test_load_city_slugs_reads_the_mapping(tmp_path, utils):
    slugs = utils.load_city_slugs(
        database_location=_scratch_cities(tmp_path, with_slug=True)
    )

    assert slugs == {"Tel Aviv": {"slug": "Tel-Aviv-Yafo", "city_id": "6845"}}


def test_load_city_slugs_tolerates_the_old_shape(tmp_path, utils):
    """A table written before resolution existed has nothing to inherit."""
    assert (
        utils.load_city_slugs(
            database_location=_scratch_cities(tmp_path, with_slug=False)
        )
        == {}
    )


def test_resolve_city_rows_annotates_each_row(utils):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return [
                {"label": "London, United Kingdom", "value": "1000"},
                {"label": "London, Canada", "value": "2000"},
            ]

    rows = utils.resolve_city_rows(
        [{"name": "London", "country": "", "description": "big"}],
        fetch=lambda *a, **k: Response(),
    )

    assert rows[0]["state"] == "ambiguous"
    assert len(rows[0]["matches"]) == 2
    assert rows[0]["name"] == "London"


def test_resolve_city_rows_skips_blank_names(utils):
    rows = utils.resolve_city_rows(
        [{"name": "  ", "country": "", "description": ""}],
        fetch=lambda *a, **k: None,
    )

    assert rows == []


def test_apply_resolution_attaches_the_slug_and_id(utils):
    cities = [{"name": "London", "country": "", "description": "big"}]

    final = utils.apply_resolution(
        cities, {"London": {"slug": "London", "city_id": "1000"}}
    )

    assert final == [
        {
            "name": "London",
            "country": "",
            "description": "big",
            "numbeo_slug": "London",
            "numbeo_city_id": "1000",
        }
    ]


def test_apply_resolution_drops_removed_and_unresolved_rows(utils):
    """An unresolved city must never reach raw_config, even if Confirm leaks."""
    cities = [
        {"name": "London", "country": "", "description": "big"},
        {"name": "Nowhereville", "country": "", "description": "made up"},
        {"name": "Munich", "country": "Germany", "description": "home"},
    ]

    final = utils.apply_resolution(
        cities,
        {
            "London": {"slug": "London", "city_id": "1000"},
            "Nowhereville": {"drop": True},
            # Munich has no pick at all -> no slug -> not written
        },
    )

    assert [row["name"] for row in final] == ["London"]
