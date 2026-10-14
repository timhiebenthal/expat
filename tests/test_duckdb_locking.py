"""dbt must not hold the warehouse open inside the app process.

dbt-duckdb keeps its DuckDB handle alive for the lifetime of the process it runs
in. A dbtRunner().invoke() inside Streamlit therefore pins the write lock on the
warehouse for as long as the app is up, and everything after it - the loaders,
the next dbt run - dies with

    IOException: Could not set lock on file ... Conflicting lock is held in ...
    (PID <the streamlit process>)

Closing the runner does not help: the handle survives del + gc.collect(). The
only reliable fix is to run dbt in its own process, which is what these tests
pin down.
"""

import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STREAMLIT_DIR = os.path.join(REPO_ROOT, "streamlit")


@pytest.fixture(scope="module")
def app_utils():
    sys.path.insert(0, STREAMLIT_DIR)
    sys.modules.pop("utils", None)
    import utils

    return utils


def duckdb_fds_open_in_this_process(needle="dwh.duckdb"):
    """Paths of open file descriptors pointing at the warehouse."""
    hits = []
    for fd in os.listdir("/proc/self/fd"):
        try:
            target = os.readlink(f"/proc/self/fd/{fd}")
        except OSError:  # fd closed while we listed
            continue
        if needle in target:
            hits.append(target)
    return hits


@pytest.fixture
def warehouse(tmp_path):
    """A private copy, so the test never touches the repo's own database."""
    source = os.path.join(REPO_ROOT, "database", "dwh.duckdb")
    if not os.path.exists(source):
        pytest.skip("no warehouse to copy")
    target = tmp_path / "dwh.duckdb"
    with open(source, "rb") as src, open(target, "wb") as dst:
        while chunk := src.read(1024 * 1024):
            dst.write(chunk)
    return target


def test_duckdb_fds_are_detectable_at_all(app_utils, warehouse):
    """Canary for the checks below: if this finds nothing, they prove nothing."""
    import duckdb

    dwh = duckdb.connect(str(warehouse))
    try:
        assert duckdb_fds_open_in_this_process()
    finally:
        dwh.close()

    assert not duckdb_fds_open_in_this_process()


def test_run_dbt_holds_no_lock_once_it_returns(app_utils, warehouse, monkeypatch):
    """The regression: dbtRunner().invoke() leaves the handle open, run_dbt does not."""
    monkeypatch.setenv("DUCKDB_LOCATION", str(warehouse))

    assert app_utils.run_dbt(["build", "--target", "prod"]), "dbt build failed"

    assert not duckdb_fds_open_in_this_process(), (
        "the app process still holds the warehouse open after dbt returned"
    )


def test_dbt_is_invoked_out_of_process(app_utils, monkeypatch):
    """A subprocess takes the lock and gives it back; in-process does not."""
    import subprocess

    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    # monkeypatch, not a manual set/del: `app_utils.subprocess` IS the subprocess
    # module, so `del app_utils.subprocess.run` removed subprocess.run for the
    # rest of the session. Any later import that shells out (dlt -> croniter ->
    # platform.architecture -> subprocess.check_output) then died with
    # "NameError: name 'run' is not defined".
    monkeypatch.setattr(app_utils.subprocess, "run", fake_run)

    app_utils.run_dbt(["deps"])

    command = seen["command"]
    assert command[0].endswith("dbt"), command
    assert command[1] == "deps"
    assert "--project-dir" in command and "--profiles-dir" in command
