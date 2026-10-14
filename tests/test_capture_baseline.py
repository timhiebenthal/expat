"""The baseline capture is the migration's one irreversible step.

Once dlt stops writing ``raw_*``, the pipeline's inputs cannot be reconstructed,
so the capture has to freeze the warehouse exactly as it stands and rename every
dbt output to the name Bruin will produce. These tests pin the parts that would
silently corrupt a baseline: clobbering an existing one, mis-naming a target, or
carrying a table that has no target at all.
"""

import importlib.util
import json
from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "capture_baseline.py"


@pytest.fixture(scope="module")
def capture_baseline():
    spec = importlib.util.spec_from_file_location("capture_baseline", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_warehouse(path):
    """A miniature warehouse shaped like the real one after a dbt build."""
    con = duckdb.connect(str(path))
    con.execute("create schema raw_config")
    con.execute("create schema raw_numbeo")
    con.execute("create schema raw_forex")
    con.execute("create schema raw_earnings")
    con.execute("create schema analytics")

    con.execute(
        "create table raw_config.cities as "
        "select * from (values ('Munich'), ('Berlin')) t(name)"
    )
    con.execute(
        "create table raw_config.jobs as "
        "select * from (values ('Data Scientist', 5.0)) t(job_title, years_experience)"
    )
    con.execute("create table raw_numbeo.cost_of_living as select 'Munich' city")
    con.execute(
        "create table raw_numbeo.cost_of_living__data as select 'Meal' category"
    )
    con.execute(
        "create table raw_earnings.job_earnings as "
        "select 'Munich' city, "
        "'Data Scientist with 5 years of experience' jobtitle_and_experience"
    )
    con.execute(
        "create table raw_forex.forex_daily as "
        "select 'EUR' from_currency, 'EUR' to_currency"
    )

    # The 13-model dbt output, under the names it currently produces. `activity`,
    # `cost_of_living` and `job_earnings` have no layer prefix yet; `core__` is
    # what the migration renames them to.
    for table in [
        "clean__config_cities",
        "clean__config_jobs",
        "clean__job_earnings",
        "clean__forex_forex_daily",
        "clean__numbeo_cost_of_living",
        "prep__avg_forex_rate",
        "prep__job_earnings",
        "prep__numbeo_cost_of_living",
    ]:
        con.execute(f"create table analytics.{table} as select 1 as value")
    con.execute("create table analytics.activity as select 'Mobility' activity_name")
    con.execute("create table analytics.cost_of_living as select 'Munich' city_name")
    con.execute("create table analytics.job_earnings as select 'Munich' city_name")

    # No Bruin target: the dataset is dropped, the child is flattened away.
    con.execute(
        "create table analytics.dataset__cost_earnings_comparison as select 1 as x"
    )
    con.execute(
        "create table analytics.clean__numbeo_cost_of_living_data as select 1 as y"
    )
    con.close()


@pytest.fixture
def warehouse(tmp_path):
    path = tmp_path / "warehouse.duckdb"
    build_warehouse(path)
    return path


def baseline_table_names(baseline):
    con = duckdb.connect(str(baseline), read_only=True)
    try:
        return {
            row[0]
            for row in con.execute(
                "select table_name from information_schema.tables "
                "where table_schema = 'baseline'"
            ).fetchall()
        }
    finally:
        con.close()


def test_refuses_to_clobber_an_existing_baseline(capture_baseline, warehouse, tmp_path):
    baseline = tmp_path / "baseline" / "dwh.duckdb"
    baseline.parent.mkdir(parents=True)
    baseline.write_bytes(b"not really a warehouse")

    with pytest.raises(SystemExit, match="refusing to overwrite"):
        capture_baseline.capture(warehouse, baseline, run_dbt=False)


def test_app_read_tables_land_under_their_bruin_names(
    capture_baseline, warehouse, tmp_path
):
    baseline = tmp_path / "baseline" / "dwh.duckdb"
    capture_baseline.capture(warehouse, baseline, run_dbt=False)

    names = baseline_table_names(baseline)

    assert {"core__activity", "core__cost_of_living", "core__job_earnings"} <= names
    # Renamed, not duplicated alongside the dbt-era name.
    assert "activity" not in names
    assert "job_earnings" not in names


def test_tables_with_no_bruin_target_are_left_out(capture_baseline, warehouse, tmp_path):
    baseline = tmp_path / "baseline" / "dwh.duckdb"
    capture_baseline.capture(warehouse, baseline, run_dbt=False)

    names = baseline_table_names(baseline)

    # dataset__cost_earnings_comparison is dropped by the migration, and the
    # numbeo child table is flattened into its parent, so neither has a target.
    assert "dataset__cost_earnings_comparison" not in names
    assert "clean__numbeo_cost_of_living_data" not in names


def test_raw_inputs_survive_and_the_manifest_records_them(
    capture_baseline, warehouse, tmp_path
):
    baseline = tmp_path / "baseline" / "dwh.duckdb"
    manifest = capture_baseline.capture(warehouse, baseline, run_dbt=False)

    con = duckdb.connect(str(baseline), read_only=True)
    try:
        raw = {
            (row[0], row[1])
            for row in con.execute(
                "select table_schema, table_name from information_schema.tables"
            ).fetchall()
        }
    finally:
        con.close()

    assert ("raw_config", "cities") in raw
    assert ("raw_earnings", "job_earnings") in raw

    assert manifest["config"]["cities"] == ["Munich", "Berlin"]
    assert manifest["config"]["jobs"] == [
        {"job_title": "Data Scientist", "years_experience": 5.0}
    ]
    assert manifest["raw_tables"]["raw_config.cities"] == 2
    assert manifest["raw_tables"]["raw_earnings.job_earnings"] == 1
    assert manifest["baseline_tables"]["core__job_earnings"] == 1
    assert manifest["captured_at"]


def test_manifest_is_written_beside_the_baseline(capture_baseline, warehouse, tmp_path):
    baseline = tmp_path / "baseline" / "dwh.duckdb"
    capture_baseline.capture(warehouse, baseline, run_dbt=False)

    manifest_path = baseline.parent / "manifest.json"
    written = json.loads(manifest_path.read_text())
    assert written["config"]["cities"] == ["Munich", "Berlin"]
