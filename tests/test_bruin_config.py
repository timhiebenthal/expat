"""Bruin's config must sit at the repo root and take the warehouse path from
the environment.

Two failure modes this guards, both called out in SPEC.md:

- ``.bruin.yml`` is resolved from the git root, so a copy next to ``pipeline/``
  is silently ignored.
- an unset ``${DUCKDB_LOCATION}`` is left as the literal string rather than
  erroring, so the path has to stay a placeholder - expanded or hardcoded, the
  "unset fails silently" guard is defeated.
"""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


def load(path):
    return yaml.safe_load(path.read_text())


def duckdb_connections():
    config = load(REPO_ROOT / ".bruin.yml")
    environment = config["environments"][config["default_environment"]]
    return environment["connections"]["duckdb"]


def test_bruin_config_lives_at_the_repo_root():
    assert (REPO_ROOT / ".bruin.yml").exists()


def test_duckdb_connection_reads_the_path_from_the_environment():
    assert [c["path"] for c in duckdb_connections()] == ["${DUCKDB_LOCATION}"]


def test_pipeline_declares_the_default_connection():
    pipeline = load(REPO_ROOT / "pipeline" / "pipeline.yml")

    assert pipeline["default_connections"]["duckdb"] == "duckdb-default"
    assert duckdb_connections()[0]["name"] == "duckdb-default"
