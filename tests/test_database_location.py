"""DuckDB location resolution.

Host runs have no shell export of DUCKDB_LOCATION and uv does not load .env on
its own, so `make streamlit_app` used to die with KeyError: 'DUCKDB_LOCATION' the
moment a page touched DuckDB. Docker and Cloud Run set the variable for real and
must keep winning over .env.

Each case runs in a subprocess because `utils` is cached in sys.modules and the
two modules (loading/ and streamlit/) share the name.
"""

import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT = os.path.join(REPO_ROOT, "database", "dwh.duckdb")


def resolve(module_dir, env_overrides):
    env = {key: value for key, value in os.environ.items() if key != "DUCKDB_LOCATION"}
    env.update(env_overrides)
    script = (
        f"import sys; sys.path.insert(0, {module_dir!r}); "
        "import utils; print(utils.DATABASE_LOCATION)"
    )

    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


@pytest.mark.parametrize("module_dir", ["loading", "streamlit"])
def test_falls_back_to_the_warehouse_when_unset(module_dir):
    assert resolve(module_dir, {}) == DEFAULT


@pytest.mark.parametrize("module_dir", ["loading", "streamlit"])
def test_real_environment_wins(module_dir):
    assert resolve(module_dir, {"DUCKDB_LOCATION": "/tmp/other.duckdb"}) == (
        "/tmp/other.duckdb"
    )


@pytest.mark.parametrize("module_dir", ["loading", "streamlit"])
def test_relative_path_is_anchored_at_the_repo_root(module_dir):
    """A relative value in .env must not depend on the working directory."""
    assert resolve(module_dir, {"DUCKDB_LOCATION": "database/dwh.duckdb"}) == DEFAULT
