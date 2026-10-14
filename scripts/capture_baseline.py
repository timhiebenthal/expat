"""Capture the frozen Bruin-parity baseline from the current warehouse.

Run once, before any migration work. This is the migration's one irreversible
step: once dlt stops writing ``raw_*``, the inputs cannot be reconstructed, so
the warehouse is copied to ``baseline/dwh.duckdb`` and every dbt output is
renamed to the name Bruin will produce, under a ``baseline.`` schema.

Historical note: this script runs the final `dbt build`, and dbt was removed from
the repo once the Bruin pipeline reached parity. It is kept as the record of how
the frozen baseline was made; running it today would fail at that step.

The copy is a *different file* from the one the app opens, which is the whole
point: a writer holds an exclusive DuckDB lock, so parity runs cannot touch
``database/dwh.duckdb`` while the app is up.

A manifest beside the copy records the config in force at capture and per-table
row counts, so a later config change is distinguishable from a port bug.

Refuses to overwrite an existing baseline: the capture is irreversible, so a
second run has to be a deliberate act.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = REPO_ROOT / "database" / "dwh.duckdb"
DEFAULT_BASELINE = REPO_ROOT / "baseline" / "dwh.duckdb"
MANIFEST_NAME = "manifest.json"
BRUIN_CLI_TAG = "v0.11.778"

# dbt output table -> the table name Bruin will produce. `dataset__...` has no
# successor and the numbeo `__data` child is flattened into its parent, so
# neither earns a baseline table. Everything else keeps its name; only the
# three entity tables gain the `core__` prefix.
TARGET_TABLES = {
    "clean__config_cities": "clean__config_cities",
    "clean__config_jobs": "clean__config_jobs",
    "clean__job_earnings": "clean__job_earnings",
    "clean__forex_forex_daily": "clean__forex_forex_daily",
    "clean__numbeo_cost_of_living": "clean__numbeo_cost_of_living",
    "prep__avg_forex_rate": "prep__avg_forex_rate",
    "prep__job_earnings": "prep__job_earnings",
    "prep__numbeo_cost_of_living": "prep__numbeo_cost_of_living",
    "activity": "core__activity",
    "cost_of_living": "core__cost_of_living",
    "job_earnings": "core__job_earnings",
}

# The frozen inputs parity runs against, recorded so a stale capture is visible.
RAW_TABLES = [
    ("raw_config", "cities"),
    ("raw_config", "jobs"),
    ("raw_numbeo", "cost_of_living"),
    ("raw_numbeo", "cost_of_living__data"),
    ("raw_forex", "forex_daily"),
    ("raw_earnings", "job_earnings"),
]


def capture(source, baseline, *, run_dbt=True, now=None):
    """Copy the warehouse, rename the targets, and return the manifest."""
    source = Path(source).resolve()
    baseline = Path(baseline).resolve()

    if not source.exists():
        raise SystemExit(f"source warehouse not found: {source}")
    if baseline.exists():
        raise SystemExit(
            f"baseline already exists at {baseline} - refusing to overwrite it. "
            "The capture is irreversible; delete it deliberately to re-capture."
        )

    if run_dbt:
        run_dbt_build(source)

    checkpoint(source)
    baseline.parent.mkdir(parents=True, exist_ok=True)
    copy_with_wal(source, baseline)

    con = duckdb.connect(str(baseline))
    try:
        materialize_baseline_tables(con)
        manifest = build_manifest(con, source, now=now)
    finally:
        con.close()

    (baseline.parent / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def run_dbt_build(source):
    """Bring ``analytics.*`` current, so the baseline is a deliberate snapshot.

    Uses this interpreter's own dbt, the way the app does, and passes the source
    path through ``DUCKDB_LOCATION`` because dbt reads the warehouse via
    ``env_var()``.
    """
    dbt_dir = REPO_ROOT / "dbt"
    dbt = Path(sys.executable).with_name("dbt")
    env = {**os.environ, "DUCKDB_LOCATION": str(source)}

    commands = []
    if not (dbt_dir / "dbt_packages" / "dbt_utils").exists():
        commands.append(["deps"])
    commands.append(["build", "--target", "prod"])

    for args in commands:
        command = [
            str(dbt),
            *args,
            "--profiles-dir",
            str(dbt_dir),
            "--project-dir",
            str(dbt_dir),
        ]
        result = subprocess.run(command, env=env, capture_output=True, text=True)
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        if result.returncode != 0:
            raise SystemExit(f"dbt {' '.join(args)} failed with exit code {result.returncode}")


def checkpoint(path):
    """Flush any WAL into the main file so a plain file copy is complete.

    Opening read-write also takes the exclusive lock, which is how the capture
    fails loudly if the Streamlit app is still holding the warehouse open.
    """
    con = duckdb.connect(str(path))
    try:
        con.execute("checkpoint")
    finally:
        con.close()


def copy_with_wal(source, baseline):
    shutil.copy2(source, baseline)
    wal = Path(str(source) + ".wal")
    if wal.exists():
        shutil.copy2(wal, Path(str(baseline) + ".wal"))


def materialize_baseline_tables(con):
    con.execute("create schema if not exists baseline")
    for source_name, target in TARGET_TABLES.items():
        con.execute(
            f'create or replace table baseline."{target}" as '
            f'select * from analytics."{source_name}"'
        )


def build_manifest(con, source, *, now=None):
    captured_at = (now or dt.datetime.now()).isoformat(timespec="seconds")
    return {
        "captured_at": captured_at,
        "source": str(source),
        "bruin_cli_tag": BRUIN_CLI_TAG,
        "config": read_config(con),
        "baseline_tables": {
            target: row_count(con, "baseline", target) for target in TARGET_TABLES.values()
        },
        "raw_tables": {
            f"{schema}.{table}": row_count(con, schema, table)
            for schema, table in RAW_TABLES
        },
    }


def read_config(con):
    cities = [
        row[0] for row in con.execute('select "name" from raw_config.cities').fetchall()
    ]
    jobs = [
        {"job_title": row[0], "years_experience": row[1]}
        for row in con.execute(
            'select "job_title", cast("years_experience" as double) '
            'from raw_config.jobs'
        ).fetchall()
    ]
    return {"cities": cities, "jobs": jobs}


def row_count(con, schema, table):
    return con.execute(f'select count(*) from "{schema}"."{table}"').fetchone()[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument(
        "--no-dbt",
        action="store_true",
        help="skip the final dbt build; copy analytics.* exactly as it stands",
    )
    args = parser.parse_args(argv)

    manifest = capture(args.source, args.baseline, run_dbt=not args.no_dbt)

    print(f"Baseline captured at {args.baseline}")
    print(f"  config: {len(manifest['config']['cities'])} cities, "
          f"{len(manifest['config']['jobs'])} jobs")
    for name, count in manifest["baseline_tables"].items():
        print(f"  baseline.{name}: {count} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
