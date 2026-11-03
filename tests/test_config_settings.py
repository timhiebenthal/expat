"""The app-owned config, written by the entry mask and read by the pages.

The Member count lives here rather than in the pipeline: nothing downstream
consumes it, so it is a rendering input kept next to the cities and jobs the mask
already owns. Its absence has to be survivable - a warehouse written before the
household existed, or a fresh clone with no warehouse at all, must still open the
comparison at one Member rather than fail.
"""

import os
import sys

import pandas as pd
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STREAMLIT_DIR = os.path.join(REPO_ROOT, "streamlit")

sys.path.insert(0, STREAMLIT_DIR)

import utils  # noqa: E402


@pytest.fixture
def warehouse(tmp_path, monkeypatch):
    """A warehouse of this test's own, so the app's is never written to."""
    target = tmp_path / "dwh.duckdb"
    monkeypatch.setattr(utils, "DATABASE_LOCATION", str(target))
    return target


def test_a_household_of_two_round_trips(warehouse):
    utils.save_config_to_duckdb(
        city_df=pd.DataFrame({"name": ["Berlin", "Munich"]}),
        jobs_df=pd.DataFrame(
            {"Job Title": ["Data Engineer"], "Years of Experience": [7]}
        ),
        members=2,
    )

    assert utils.load_config()["members"] == 2
    assert utils.load_members() == 2


def test_a_household_of_one_round_trips(warehouse):
    utils.save_config_to_duckdb(
        city_df=pd.DataFrame({"name": ["Berlin"]}),
        jobs_df=pd.DataFrame(
            {"Job Title": ["Data Engineer"], "Years of Experience": [7]}
        ),
        members=1,
    )

    assert utils.load_members() == 1


def test_a_warehouse_without_settings_means_one_member(warehouse):
    import duckdb

    dwh = duckdb.connect(str(warehouse))
    try:
        dwh.sql("create schema if not exists raw_config")
        dwh.sql("create or replace table raw_config.jobs as select 'x' as job_title")
    finally:
        dwh.close()

    assert utils.load_members() == 1


def test_no_warehouse_at_all_means_one_member(tmp_path, monkeypatch):
    monkeypatch.setattr(
        utils, "DATABASE_LOCATION", str(tmp_path / "not_there" / "dwh.duckdb")
    )

    assert utils.load_members() == 1
    assert not (tmp_path / "not_there").exists(), "reading one created a warehouse"


def test_jobs_without_a_title_are_dropped():
    """A Couple can have one earner, and the editor allows empty rows."""
    editor = pd.DataFrame(
        {
            "Job Title": ["Data Engineer", "", None, "  "],
            "Years of Experience": [7, None, 3, 4],
        }
    )

    kept = utils.jobs_with_titles(editor)

    assert kept["Job Title"].tolist() == ["Data Engineer"]
    assert kept["Years of Experience"].tolist() == [7]


def test_titles_are_trimmed():
    editor = pd.DataFrame(
        {"Job Title": ["  Data Engineer  "], "Years of Experience": [7]}
    )

    assert utils.jobs_with_titles(editor)["Job Title"].tolist() == ["Data Engineer"]


def test_the_editor_opens_with_a_second_row_for_a_couple():
    """An affordance, not a rule: the Member count is chosen above the editor."""
    single = utils.jobs_editor_default(1)
    couple = utils.jobs_editor_default(2)

    assert len(single) == 1
    assert len(couple) == 2
    assert couple["Job Title"].tolist() == ["Data Engineer", ""]


def test_a_blank_second_row_never_reaches_the_config():
    """What the couple's affordance hands over must survive being written."""
    couple = utils.jobs_editor_default(2)

    assert utils.jobs_with_titles(couple)["Job Title"].tolist() == ["Data Engineer"]
