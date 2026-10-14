# Spec: Migrate the pipeline from dlt + dbt to Bruin

## Objective

Replace dlt (ingestion), dbt (transformation) and the hand-rolled orchestration in `streamlit/utils.py` with a single Bruin pipeline, both to cut the number of moving parts in a solo hobby project and to get real experience with Bruin.

The user is one person: the owner of the project. There is no authentication, no multi-tenancy, and no consumer other than the Streamlit app. Success is **data parity with the current dbt output** - no new features, no behaviour changes.

Scope covers ingestion and transformation. `loading/` and `dbt/` are abandoned, then deleted once parity is proven.

## Baseline

Parity is impossible to check against a live re-run, because the pipeline is not deterministic across runs. numbeo prices are re-scraped live, yfinance returns a rolling 365-day window ending yesterday so the average FX rate drifts daily, and the LLM returns different salaries each run. Re-ingesting therefore produces legitimately different Raw data, and any value comparison would flag differences unrelated to the port.

The baseline is a gitignored copy of the warehouse at `baseline/dwh.duckdb`, captured **before any migration work**, holding:

1. `raw_*` exactly as dlt left them.
2. `baseline.<target name>` - the final dbt output renamed to the names Bruin will produce, so comparison is a direct `EXCEPT ALL` with no name translation.
3. A manifest recording the config in force at capture, the capture timestamp, and per-source row counts. Without it, a config change between capture and comparison is indistinguishable from a port bug.

### The pipeline takes no arguments

Every input is a row in the database, not a parameter, which is why there is nothing to pass on the command line. Every asset is also full-replace, so date-range flags do not apply either.

| Input | Lives in | Written by |
|---|---|---|
| cities and jobs | `raw_config.cities`, `raw_config.jobs` | the app form |
| numbeo prices | `raw_numbeo.*` | ingest |
| FX rates | `raw_forex.forex_daily` | ingest |
| salaries | `raw_earnings.job_earnings` | ingest |

All four sit in the same file, so reproducibility comes from **which file `DUCKDB_LOCATION` points at**, not from flags. Pointing at the baseline copy freezes all of them together, including the config: the app never writes to that copy, so its `raw_config` rows stay exactly as captured. The baseline copy *is* the predefined input set - no separate fixture mechanism is needed.

One consequence: what the baseline means depends on which config was in force at capture. Capturing must therefore begin from a deliberate city and job list, recorded in the manifest. The current live config is the sensible choice, since it keeps the before and after directly comparable; adding cities beforehand is a cheap way to widen coverage while the capture is free.

Capturing this is the one irreversible step: once dlt stops writing `raw_*`, the inputs cannot be reconstructed.

Parity work points `DUCKDB_LOCATION` at this copy rather than at `database/dwh.duckdb`, so the app's own warehouse is never in play and the app never has to be stopped. That matters because DuckDB's lock is exclusive: a writer blocks every other open, including read-only ones, so `bruin data-diff` would be refused outright against a file the app is holding.

## Tech Stack

- **Bruin CLI**, pinned to an exact tag (`v0.11.778`, confirmed to exist), installed into the existing app image at build time rather than by adopting Bruin's own container image - the container is the Streamlit app, and Bruin runs inside it.
- **DuckDB**, the single file at `$DUCKDB_LOCATION` (`database/dwh.duckdb` on the host, `/app/database/dwh.duckdb` in the container).
- **Python assets** resolving dependencies from the repo's existing `pyproject.toml` + `uv.lock`. Bruin walks up from the asset to the repo root to find them.
- **Streamlit**, **Docker** and **Cloud Run** unchanged.
- **pytest** unchanged as the Python test runner.
- Vocabulary per `GLOSSARY.md`: layers `clean` / `prep` / `core` / `mart`; Cost item, Frequency, Monthly cost, Cost group.

## Commands

```bash
# Install the CLI, pinned. It is a Go binary, not a PyPI package.
# On the host:
curl -LsSf https://getbruin.com/install/cli | sh -s v0.11.778
# In the image, where it must land somewhere the non-root app user can execute:
#   RUN curl -LsSf https://getbruin.com/install/cli | sh -s -- -b /usr/local/bin v0.11.778

# The database path is interpolated from the environment into .bruin.yml. An
# UNSET var is left as the literal string "${DUCKDB_LOCATION}" with no error,
# so this must always be exported first.
export DUCKDB_LOCATION=database/dwh.duckdb

bruin validate pipeline
bruin run pipeline

bruin run pipeline/assets/ingest/numbeo.py
bruin render pipeline/assets/core/cost_of_living.sql

# --- Parity work ---------------------------------------------------------
# Runs against the baseline copy, a DIFFERENT file from the one the app opens,
# so the app does not need stopping. This matters because a writer holds an
# exclusive lock: even a read-only open is refused while the app is running.
export DUCKDB_LOCATION=baseline/dwh.duckdb

# Transforms only, over frozen Raw inputs. Selected assets do NOT drag in their
# upstreams, so this never re-fetches. A directory argument would NOT work here
# - it is read as a pipeline root, not a folder scope.
bruin run pipeline --selector "tag:layer:transform"

# Same thing by path, if tags are not yet in place
bruin run pipeline --selector "path:assets/clean path:assets/prep path:assets/core"

# Parity gate 1: schema and row counts. --full is NOT usable here - its
# numerical-statistics step crashes on DuckDB DECIMAL columns.
bruin data-diff --connection duckdb-default --fail-if-diff \
  "baseline.core__cost_of_living" "analytics.core__cost_of_living"

# Parity gate 2: exact row equality. Both counts must be 0.
duckdb baseline/dwh.duckdb -c "
  select
    (select count(*) from (select * from baseline.core__cost_of_living
                           except all select * from analytics.core__cost_of_living)) as only_in_baseline,
    (select count(*) from (select * from analytics.core__cost_of_living
                           except all select * from baseline.core__cost_of_living)) as only_in_bruin;"

uv run pytest tests -q
uv run streamlit run streamlit/Home.py
make local_build && make local_deploy
```

## Project Structure

```
.bruin.yml                  Connections + environments. MUST sit at the repo root.
pipeline/                   Bruin pipeline root
  pipeline.yml              Pipeline definition
  assets/
    ingest/                 Python assets writing flat Raw tables
    clean/  prep/  core/  mart/   One folder per layer
  lib/                      Shared Python helpers. NOT under assets/ - see below.
  macros/                   Jinja macros, auto-loaded, .sql only
baseline/                   Gitignored. Frozen warehouse + capture manifest.
tests/                      pytest, unchanged location
docs/adr/                   Decisions, including 0001-migrate-to-bruin.md
GLOSSARY.md
streamlit/                  Unchanged except the pipeline trigger
loading/  dbt/              Dead at cutover; removed in the final commit
```

Four things worth stating because they are easy to get wrong:

- **`.bruin.yml` must be at the repo root.** Bruin resolves it from the git root, and a copy next to `pipeline/` is silently ignored unless `--config-file` or `BRUIN_CONFIG_FILE` is set.
- **Never put shared Python under `assets/`.** Bruin walks that directory recursively for `.py` and would treat a helper module as an asset. Helpers live in `pipeline/lib/`.
- **Set `name:` explicitly in every asset header.** Bruin otherwise infers the name from the path, which makes renames silently change table names.
- **Assets are named `<layer>__<thing>` in one schema**, e.g. `analytics.clean__numbeo_cost_of_living`. `clean__` and `prep__` already match today's names; `core__` is new, so the three tables the app queries are renamed in the app-trigger task.

Model count goes from 13 to 11: flattening removes `clean__numbeo_cost_of_living_data`, and dropping the unread Mart removes `dataset__cost_earnings_comparison`.

## Code Style

Python assets stay thin. All real logic lives in `pipeline/lib/`, is free of network calls, and is therefore directly testable. `materialize()` only orchestrates and returns rows - Bruin imports the module and calls it with no arguments.

```python
"""@bruin
name: raw_numbeo.cost_of_living
image: python:3.13
connection: duckdb-default

materialization:
  type: table
  strategy: create+replace

tags:
  - layer:ingest
@bruin"""

from pipeline.lib.numbeo import fetch_city_costs, configured_cities


def materialize():
    rows = []
    for city in configured_cities():
        rows.extend(fetch_city_costs(city))
    return rows
```

SQL assets carry the same header shape, with an explicit `depends` because Bruin does not infer dependencies from the SQL, and a layer tag so runs can be scoped:

```sql
/* @bruin
name: analytics.core__cost_of_living
type: duckdb.sql
depends:
  - analytics.prep__numbeo_cost_of_living
  - analytics.prep__avg_forex_rate
tags:
  - layer:transform
  - layer:core
@bruin */

select ...
```

Conventions: snake_case for table and column names, `<layer>__<subject>` for asset names, one asset per file, no logic in `materialize()` beyond orchestration, and a `layer:` tag on every asset.

## Testing Strategy

Four layers. None of them is a coverage gate.

1. **pytest** (`uv run pytest tests`) for pure Python. The existing assertions carry over, with imports re-pointed at `pipeline/lib/`, because Bruin assets are ordinary importable modules - `from pipeline.assets.ingest import numbeo` then `numbeo.materialize()` works. Keep anything that touches the network behind an injectable function so tests never need Bruin, an API key or a live source.
2. **Quality checks** on the assets: the four current dbt tests become one built-in `not_null` and three `custom_checks`. Each must be observed failing against deliberately broken input before it is trusted.
3. **Transform parity** (the port gate, values matter). Run only the transform assets against the baseline copy, so they read frozen Raw inputs, then gate the **entity** tables the app reads - `core__cost_of_living`, `core__activity`, `core__job_earnings` - with both gates below. `clean__*` and `prep__*` are internal: the transform run exercises them, but their output may change where the rewrite needs it.
4. **Ingest parity** (grain only). Run each ingest asset against a scratch copy and confirm the grain, and the columns the entity tables depend on. Column-for-column parity with the dlt-era Raw tables is not required - the ingest defines the new Raw contract.

`bruin unit-test` is deliberately **not** used: it rejects `.py` assets outright, and its DuckDB support is mechanically present but not vendor-verified.

**Two parity gates, because neither is sufficient alone.**

`bruin data-diff` compares schema and row counts. (`--full` would add column statistics - min/max/avg/sum/stddev, distinct counts, fill rate - but on v0.11.778 that step crashes on any DuckDB `DECIMAL` column with "cannot assign decimal128.Num to float64", and these tables have several, so gate 1 runs without it.) It never joins on keys and never compares rows positionally, so it can pass while individual rows are wrong - and row-level loss is the exact failure this project keeps hitting. Use it as the cheap first pass, then require exact row equality with a bidirectional `EXCEPT ALL`, which is multiset equality and catches duplicate-count drift too. The reconciliation queries are committed (`scripts/parity.sql`) rather than run ad hoc, so Success Criteria are reproducible.

## Boundaries

**Always**
- Run `uv run pytest tests` and both parity gates before committing a migration step.
- Pin the Bruin CLI to an exact tag, locally and in the container.
- Keep `materialize()` thin, with the real logic in named, network-free functions under `pipeline/lib/`.
- Set `name:` explicitly and tag `layer:` on every asset.
- Export `DUCKDB_LOCATION` before any Bruin command, since an unset var fails silently into a literal path.

**Ask first**
- Deleting `loading/` or `dbt/`, or removing `dlt` / `dbt-core` / `dbt-duckdb` from `pyproject.toml`.
- Changing the `raw_*` contract once ingest has landed.
- Renaming the Cost item vocabulary again.
- Adding a dependency, Bruin-side or Python-side.

**Never**
- Commit `.env`, secrets, or the baseline warehouse binary.
- Start a Bruin run while the Streamlit app holds the DuckDB file open.
- Write to `raw_*` from Streamlit; only `raw_config` is app-owned.
- Weaken or delete a check to make a build pass.

## Success Criteria

- `bruin run pipeline` completes with every asset succeeding against a fresh copy of the warehouse.
- Transform parity: running only the transforms against the baseline copy yields 0 rows from both directions of the `EXCEPT ALL` on every table the app reads, and `data-diff --full --fail-if-diff` reports no differences.
- Ingest parity: each Raw table has the grain the entity tables expect, recorded as an explicit check. Column-for-column parity with the dlt-era tables is not required.
- All four quality checks exist and have each been seen failing on deliberately broken input.
- `uv run pytest tests` passes, with the same or greater coverage of the logic currently in `loading/`.
- The app's "Submit Cities" button runs the whole pipeline end to end and the Comparison page renders.
- `dlt`, `dbt-core` and `dbt-duckdb` are gone from `pyproject.toml`, `loading/` and `dbt/` are deleted, and the container still builds and serves the app.

### Settled during specification

- **Prefixes are uniform.** `core__` and `mart__` join `clean__` and `prep__`. This changes the three table names the app queries (`analytics.cost_of_living` and friends), which is a small deliberate edit rather than an accident of convention.
- **Extracted `loading/` logic lands in `pipeline/lib/`.** The pure helpers (`parse_table_rows`, `build_ticker`, `build_job_string`, `attach_city_records`, `assert_every_city_came_back`) move there and the pytest suite is re-pointed, so deleting `loading/` cannot delete the parts that are actually tested.
- **`read_only` interpolation is not needed.** Nothing reads the warehouse through Bruin, so no boolean is ever interpolated; only the connection path needs `${DUCKDB_LOCATION}`.
- **Bruin's container image is not used.** The CLI is curl-installed into the app image at a pinned tag, so there is no GHCR tag to chase.

### Amended during implementation

- **Parity is gated on the entity tables, not the intermediate ones.** Only the tables the app reads carry both gates; `clean__*` and `prep__*` are internal and free to change shape (dropping dlt's `_dlt_id` / `_dlt_load_id` / `_loadet_at`, flattening numbeo).
- **No Raw column parity.** The Bruin ingest defines the new Raw contract and does not reproduce dlt's metadata columns. `raw_forex.forex_daily` carries Bruin's own `_ingestr_loaded_at` / `_ingestr_run_id` instead.
- **Python assets must not set `image: python:3.13`.** Bruin resolves the interpreter from it, and `requires-python` is `>=3.11,<3.13`, so `uv lock` refuses and the asset fails at run time.
- **`create+replace` does not drop a pre-existing table.** Against a warehouse that still has dlt's tables, Bruin keeps the old columns and back-fills them with `'-'`. Cutover must drop the dlt-era `raw_*` tables so the new contract takes effect.

## Open Questions

None outstanding. Anything discovered during `transform` that contradicts this spec should be raised before the port continues, not worked around silently.
