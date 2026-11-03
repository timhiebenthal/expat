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


def test_picks_from_reads_the_slug_for_a_resolved_city(utils):
    annotated = [
        {
            "name": "Munich",
            "country": "Germany",
            "description": "",
            "state": "resolved",
            "matches": [{"label": "Munich, Germany", "value": "1111"}],
        }
    ]

    class Response:
        headers = {"Location": "https://www.numbeo.comMunich"}

        def raise_for_status(self):
            pass

    picks = utils.picks_from(annotated, fetch=lambda *a, **k: Response())

    assert picks == {"Munich": {"slug": "Munich", "city_id": "1111"}}


def test_picks_from_uses_the_chosen_match_for_an_ambiguous_city(utils):
    annotated = [
        {
            "name": "London",
            "country": "",
            "description": "",
            "state": "ambiguous",
            "matches": [
                {"label": "London, United Kingdom", "value": "1000"},
                {"label": "London, Canada", "value": "2000"},
            ],
        }
    ]

    class Response:
        headers = {"Location": "https://www.numbeo.comLondon-Canada"}

        def raise_for_status(self):
            pass

    picks = utils.picks_from(
        annotated, {"London": {"city_id": "2000"}}, fetch=lambda *a, **k: Response()
    )

    assert picks == {"London": {"slug": "London-Canada", "city_id": "2000"}}


def test_picks_from_takes_a_manual_slug_for_an_unresolved_city(utils):
    annotated = [
        {
            "name": "Nowhereville",
            "country": "",
            "description": "",
            "state": "unresolved",
            "matches": [],
        }
    ]

    picks = utils.picks_from(annotated, {"Nowhereville": {"manual": "Tel-Aviv-Yafo"}})

    assert picks == {"Nowhereville": {"slug": "Tel-Aviv-Yafo", "city_id": None}}


def test_picks_from_marks_a_dropped_city(utils):
    annotated = [
        {
            "name": "Nowhereville",
            "country": "",
            "description": "",
            "state": "unresolved",
            "matches": [],
        }
    ]

    picks = utils.picks_from(annotated, {"Nowhereville": {"drop": True}})

    assert picks == {"Nowhereville": {"drop": True}}


def test_rename_rows_resolves_the_new_name(utils):
    """A rename is a new name to match, so the row comes back resolved."""
    annotated = [
        {
            "name": "Nowhereville",
            "country": "",
            "description": "",
            "state": "unresolved",
            "matches": [],
        }
    ]

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return [{"label": "Tel Aviv-Yafo, Israel", "value": "6845"}]

    updated = utils.rename_rows(
        annotated, {"Nowhereville": "Tel Aviv"}, fetch=lambda *a, **k: Response()
    )

    assert updated[0]["name"] == "Tel Aviv"
    assert updated[0]["state"] == "resolved"
    assert updated[0]["matches"][0]["value"] == "6845"


def test_rename_rows_leaves_untouched_rows_alone(utils):
    annotated = [
        {
            "name": "Munich",
            "country": "Germany",
            "description": "",
            "state": "resolved",
            "matches": [{"label": "Munich, Germany", "value": "1111"}],
        }
    ]

    updated = utils.rename_rows(annotated, {}, fetch=None)

    assert updated == annotated


def test_the_slug_the_app_writes_is_the_one_the_ingest_reads(tmp_path, utils, monkeypatch):
    """The end of the app and the start of the ingest must agree.

    The app resolves and writes raw_config.cities; the ingest reads it back. If
    the two disagreed on the column, the stored slug would never be scraped and
    the whole feature would be inert.
    """
    import pandas as pd

    from pipeline.assets.ingest import numbeo as ingest

    annotated = [
        {
            "name": "Tel Aviv",
            "country": "Israel",
            "description": "warm",
            "state": "resolved",
            "matches": [{"label": "Tel Aviv-Yafo, Israel", "value": "6845"}],
        }
    ]

    class Redirect:
        headers = {"Location": "https://www.numbeo.comTel-Aviv-Yafo"}

        def raise_for_status(self):
            pass

    picks = utils.picks_from(annotated, fetch=lambda *a, **k: Redirect())
    rows = utils.apply_resolution(annotated, picks)

    db = tmp_path / "e2e.duckdb"
    monkeypatch.setattr(utils, "DATABASE_LOCATION", str(db))
    utils.save_config_to_duckdb(
        city_df=pd.DataFrame(rows),
        jobs_df=pd.DataFrame(
            {"job_title": ["Data Engineer"], "years_experience": [7]}
        ),
    )

    monkeypatch.setenv("DUCKDB_LOCATION", str(db))
    assert ingest.configured_cities() == [("Tel Aviv", "Tel-Aviv-Yafo")]
