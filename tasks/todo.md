# Task List: Migrate the pipeline from dlt + dbt to Bruin

Plan: `tasks/plan.md` | Contract: `SPEC.md` | Module ids: `oracle` `ingest` `transform` `quality` `app-trigger` `cutover`

---

## Phase 0: Foundations

## Task 1: Branch and capture the baseline `[oracle]`

**Description:** Create the migration branch and capture the frozen baseline before anything else changes. Run the final `dbt build` so `analytics.*` is current for a deliberate config, copy the warehouse to `baseline/dwh.duckdb`, rename the dbt output to the target names under a `baseline.` schema, and write a manifest recording the config, timestamp and row counts. This is the only irreversible step in the migration: once dlt stops writing `raw_*`, the inputs cannot be reconstructed.

**Acceptance criteria:**
- [x] The deliberate config is in `raw_config.cities` / `raw_config.jobs` and recorded in the manifest
- [x] A final `dbt build` succeeds on that config before the copy is taken
- [x] Every baseline table exists under its *target* name, e.g. `analytics.job_earnings` -> `baseline.core__job_earnings`
- [x] `dataset__cost_earnings_comparison` is excluded, since it has no target
- [x] The manifest records row counts for every baseline table and for every `raw_*` table
- [x] `baseline/` is gitignored; the capture script is committed

**Verification:**
- [x] `git status --short` shows no `baseline/` contents
- [x] `uv run python scripts/capture_baseline.py` is idempotent, or refuses to overwrite an existing baseline
- [x] A read-only DuckDB connection lists every expected `baseline.*` table
- [x] Row counts in the manifest match a fresh `count(*)` per table

**Dependencies:** None

**Files likely touched:**
- `scripts/capture_baseline.py` (new)
- `.gitignore`

**Estimated scope:** Medium

---

## Task 2: Bruin skeleton proven against DuckDB `[ingest]`

**Description:** Install the pinned CLI, add `.bruin.yml` at the repo root and a `pipeline/` containing one trivial asset, and prove the whole chain works against the baseline copy. This is the fail-fast check for the riskiest unknown: whether Bruin can drive this DuckDB file at all. No real assets yet.

**Acceptance criteria:**
- [x] CLI installed at the pinned tag and `bruin version` reports it
- [x] `.bruin.yml` sits at the repo root and connects with `path: "${DUCKDB_LOCATION}"`
- [x] `pipeline/pipeline.yml` and `pipeline/assets/probe.sql` exist; the probe writes `analytics.probe`
- [x] Running with `DUCKDB_LOCATION` unset is observed failing in the documented way, so the guard is understood rather than assumed
- [x] `analytics.probe` exists in `baseline/dwh.duckdb` afterwards and not in `database/dwh.duckdb`

**Verification:**
- [x] `bruin validate pipeline` succeeds
- [x] `bruin run pipeline` succeeds with `DUCKDB_LOCATION=baseline/dwh.duckdb`
- [x] The probe table is queryable and `database/dwh.duckdb` is unchanged (mtime)
- [x] The probe asset is deleted before Phase 2, so it never reaches a checkpoint

**Dependencies:** Task 1

**Files likely touched:**
- `.bruin.yml` (new)
- `pipeline/pipeline.yml` (new)
- `pipeline/assets/probe.sql` (new, deleted again)

**Estimated scope:** Small

---

## Checkpoint A: Foundations

- [x] Baseline captured, verified, and absent from git
- [x] `bruin validate` and `bruin run` both succeed against the baseline copy
- [x] The unset-`DUCKDB_LOCATION` failure mode has been seen, not merely read about
- [ ] Review with human before porting models

---

## Phase 1: Shared Python

Three independent streams with disjoint files; safe to parallelize.

## Task 3: Extract `pipeline/lib/numbeo.py` `[ingest]`

**Description:** Move the numbeo scraping logic out of `loading/costofliving.py` into a network-free module: table parsing, the city URL builder, and the city-completeness assertion. Keep the existing test assertions; re-point their imports. Nothing here knows about Bruin or dlt.

**Acceptance criteria:**
- [ ] `parse_table_rows`, `build_city_url` and `assert_every_city_came_back` live in `pipeline/lib/numbeo.py`
- [x] No module-level network calls; the fetch is a parameter or an injected dependency
- [x] Every existing assertion in `tests/test_costofliving.py` still passes, with imports re-pointed
- [x] `loading/costofliving.py` is left untouched and still imports (it is deleted at cutover, not now)

**Verification:**
- [x] `uv run pytest tests/test_costofliving.py -q` passes
- [x] `uv run pytest tests -q` passes in full

**Note:** `assert_every_city_came_back` does not exist in `loading/costofliving.py` - it lives in `loading/llm_earnings.py` and moves in Task 5. The numbeo completeness check is `dbt/tests/assert_all_cities_have_cost_of_living.sql`, ported in Task 10. `parse_table_rows` and `build_city_url` were extracted as-is; nothing was invented, to keep output unchanged.

**Dependencies:** None

**Files likely touched:**
- `pipeline/lib/numbeo.py` (new)
- `tests/test_costofliving.py`

**Estimated scope:** Small

---

## Task 4: Extract `pipeline/lib/forex.py` `[ingest]`

**Description:** Move the FX logic out of `loading/forex.py` into a network-free module. The ticker direction fix and the multi-index column flattening are the parts worth protecting, so they must survive with their tests.

**Acceptance criteria:**
- [x] `build_ticker` and the yfinance response flattening live in `pipeline/lib/forex.py`
- [x] The ticker asserts the `GBPEUR=X` direction, not `EURGBP=X`
- [x] The "a currency with no rows aborts rather than writing a partial table" behaviour is preserved and still tested
- [x] No module-level network calls

**Verification:**
- [x] `uv run pytest tests/test_forex.py -q` passes
- [x] `uv run pytest tests -q` passes in full

**Dependencies:** None

**Files likely touched:**
- `pipeline/lib/forex.py` (new)
- `tests/test_forex.py`

**Estimated scope:** Small

---

## Task 5: Extract `pipeline/lib/earnings.py` `[ingest]`

**Description:** Move the LLM earnings logic out of `loading/llm_earnings.py` into a network-free module: the canonical job string, the job-string stamping that overrides whatever the model returns, and the city-completeness assertion.

**Acceptance criteria:**
- [x] `build_job_string`, `attach_job_string` and `assert_every_city_came_back` live in `pipeline/lib/earnings.py`
- [x] The job string parses back to the configured title under `prep__job_earnings`' own expressions
- [x] The override of a reworded title is preserved and still tested
- [x] No module-level network calls; the LLM call is injected

**Verification:**
- [x] `uv run pytest tests/test_llm_earnings.py -q` passes
- [x] `uv run pytest tests -q` passes in full

**Dependencies:** None

**Files likely touched:**
- `pipeline/lib/earnings.py` (new)
- `tests/test_llm_earnings.py`

**Estimated scope:** Small

---

## Checkpoint B: Shared Python

- [x] `uv run pytest tests` green in full
- [x] No network calls anywhere under `pipeline/lib/`
- [x] `loading/` still imports, so the old path stays runnable until cutover

---

## Phase 2: Forex and earnings paths

## Task 6: Forex path end to end `[ingest]`

**Description:** The first real vertical slice: a Python asset fetches FX rates into a flat `raw_forex.forex_daily`, and the clean and prep SQL assets reproduce `clean__forex_forex_daily` and `prep__avg_forex_rate`. Finishes with both parity gates on those two tables against the frozen inputs.

**Acceptance criteria:**
- [ ] `pipeline/assets/ingest/forex.py` writes a flat `raw_forex.forex_daily`, with an explicit `name:` and a `layer:` tag
- [ ] `clean__forex_forex_daily` and `prep__avg_forex_rate` exist with explicit `depends`
- [ ] Both gates pass on both tables against the baseline copy
- [ ] The ingest asset's value output is *not* compared to the baseline, only its shape - FX values legitimately change

**Verification:**
- [ ] `bruin run pipeline --selector "tag:layer:transform"` succeeds
- [ ] `bruin data-diff --full --fail-if-diff` reports no differences for both tables
- [ ] Bidirectional `EXCEPT ALL` returns 0 and 0
- [ ] `bruin run pipeline/assets/ingest/forex.py` succeeds against a scratch copy and the resulting columns and types match the baseline's

**Dependencies:** Task 2, Task 4

**Files likely touched:**
- `pipeline/assets/ingest/forex.py` (new)
- `pipeline/assets/clean/forex_forex_daily.sql` (new)
- `pipeline/assets/prep/avg_forex_rate.sql` (new)
- `scripts/parity.sql` (new)

**Estimated scope:** Medium

---

## Task 7: Earnings path end to end `[ingest]`

**Description:** The second vertical slice, and the first app-visible one: a Python asset produces `raw_earnings.job_earnings`, and the clean, prep and core assets reproduce `clean__job_earnings`, `prep__job_earnings` and `core__job_earnings`. Depends on Task 6 for the FX rates that conversion needs.

**Acceptance criteria:**
- [ ] `pipeline/assets/ingest/earnings.py` writes `raw_earnings.job_earnings` with the canonical job string
- [ ] `clean__config_jobs` and `clean__job_earnings` exist
- [ ] `prep__job_earnings` matches on job title *and* experience, preserving the join that silently dropped rows before
- [ ] `core__job_earnings` matches the baseline exactly under both gates
- [ ] `assert_all_configured_jobs_have_earnings` behaviour is reproduced

**Verification:**
- [ ] `bruin run pipeline --selector "tag:layer:transform"` succeeds
- [ ] Both gates pass for `core__job_earnings`
- [ ] `uv run pytest tests -q` passes

**Dependencies:** Task 2, Task 5, Task 6

**Files likely touched:**
- `pipeline/assets/ingest/earnings.py` (new)
- `pipeline/assets/clean/config_jobs.sql` (new)
- `pipeline/assets/clean/job_earnings.sql` (new)
- `pipeline/assets/prep/job_earnings.sql` (new)
- `pipeline/assets/core/job_earnings.sql` (new)

**Estimated scope:** Medium

---

## Checkpoint C: Forex and earnings

- [ ] `core__job_earnings` matches the baseline exactly
- [ ] Forex and earnings Raw tables match the baseline's shape and grain
- [ ] Review with human before starting the cost path

---

## Phase 3: Cost path

## Task 8: Numbeo path end to end, flattened `[ingest]`

**Description:** A Python asset loads numbeo flat - one row per city, category and cost - replacing dlt's parent/child pair. The clean and prep assets then reproduce `clean__numbeo_cost_of_living` and `prep__numbeo_cost_of_living`, carrying the currency join that `core__cost_of_living` needs.

**Acceptance criteria:**
- [ ] The ingest asset returns one flat row per city/category, with no nested `data` key
- [ ] `clean__numbeo_cost_of_living` is a single model; the `__data` child model does not exist
- [ ] `clean__config_cities` exists and reads the app-owned `raw_config.cities`
- [ ] `prep__numbeo_cost_of_living` keeps the currency join and the Cost group mapping, with the duplicate group column collapsed
- [ ] Both gates pass for both transform tables

**Verification:**
- [ ] `bruin run pipeline --selector "tag:layer:transform"` succeeds
- [ ] Both gates pass for `clean__numbeo_cost_of_living` and `prep__numbeo_cost_of_living`
- [ ] The ingest asset writes the same columns as the baseline's flattened equivalent

**Dependencies:** Task 2, Task 3, Task 6

**Files likely touched:**
- `pipeline/assets/ingest/numbeo.py` (new)
- `pipeline/assets/clean/numbeo_cost_of_living.sql` (new)
- `pipeline/assets/clean/config_cities.sql` (new)
- `pipeline/assets/prep/numbeo_cost_of_living.sql` (new)

**Estimated scope:** Medium

---

## Task 9: Cost and activity core models `[transform]`

**Description:** Finish the app-visible surface: `core__cost_of_living` and `core__activity`, both built off the prep layer, with currency conversion.

**Acceptance criteria:**
- [ ] `core__cost_of_living` matches the baseline exactly under both gates
- [ ] `core__activity` matches the baseline exactly under both gates
- [ ] The remaining dbt test behaviour is reproduced where it concerns these tables
- [ ] Every model carries an explicit `name:`, `depends:` and `layer:` tag

**Verification:**
- [ ] `bruin run pipeline --selector "tag:layer:transform"` succeeds
- [ ] Both gates pass for `core__cost_of_living` and `core__activity`
- [ ] A query of all three app-read tables returns the same row counts as the baseline

**Dependencies:** Task 8

**Files likely touched:**
- `pipeline/assets/core/cost_of_living.sql` (new)
- `pipeline/assets/core/activity.sql` (new)

**Estimated scope:** Medium

---

## Checkpoint D: Full transform parity

- [ ] Every table the app reads matches the baseline exactly
- [ ] Both parity gates pass for all of them
- [ ] Review with human before touching quality

---

## Phase 4: Quality

## Task 10: Port the four checks `[quality]`

**Description:** Move the four dbt singular tests onto the Bruin assets: the null-check becomes a built-in `not_null`, and the three completeness assertions become `custom_checks`. Each must be seen failing before it is trusted, since a guard that cannot fail proves nothing.

**Acceptance criteria:**
- [ ] The `assert_amounts_are_converted` null check is expressed as `not_null` column checks
- [ ] `assert_all_cities_have_earnings`, `assert_all_cities_have_cost_of_living` and `assert_all_configured_jobs_have_earnings` exist as `custom_checks` on the appropriate assets
- [ ] Each check has been run against deliberately broken input and observed failing
- [ ] Checks are attached to the asset that would go wrong, not centralised

**Verification:**
- [ ] `bruin validate pipeline` reports the checks
- [ ] For each check: break the input, observe the failure, restore, observe the pass
- [ ] `bruin run pipeline --selector "tag:layer:transform"` succeeds when the data is sound

**Dependencies:** Task 9

**Files likely touched:**
- `pipeline/assets/core/job_earnings.sql`
- `pipeline/assets/core/cost_of_living.sql`
- `pipeline/assets/prep/numbeo_cost_of_living.sql`
- `pipeline/assets/core/activity.sql`

**Estimated scope:** Medium

---

## Checkpoint E: Quality

- [ ] All four checks present and passing on sound data
- [ ] Each one demonstrably fails on broken data, with the failure output recorded

---

## Phase 5: App trigger

## Task 11: Streamlit runs the Bruin pipeline `[app-trigger]`

**Description:** Replace the loader-and-dbt orchestration in `streamlit/utils.py` with a single `bruin run`, and rename the three tables the app queries to their `core__` names.

**Acceptance criteria:**
- [ ] `run_pipeline()` shells out to `bruin run pipeline` and fails loudly, as it does now
- [ ] `Comparison.py` and `Sandbox.py` query `analytics.core__cost_of_living`, `analytics.core__activity`, `analytics.core__job_earnings`
- [ ] No `/app/...` paths and no in-process dbt remain
- [ ] The app still closes its DuckDB connection before the subprocess starts

**Verification:**
- [ ] `uv run pytest tests -q` passes, including the page smoke tests
- [ ] `duckdb baseline/dwh.duckdb` + a manual `bruin run` produces the tables the queries expect
- [ ] Clicking "Submit Cities" in a locally run app completes the pipeline and renders the Comparison page

**Dependencies:** Task 9, Task 10

**Files likely touched:**
- `streamlit/utils.py`
- `streamlit/pages/Comparison.py`
- `streamlit/pages/Sandbox.py`

**Estimated scope:** Small

---

## Checkpoint F: App

- [ ] "Submit Cities" runs the pipeline end to end
- [ ] The Comparison page renders with all cities present
- [ ] Review with human before cutover

---

## Phase 6: Cutover

## Task 12: Remove dlt and dbt `[cutover]`

**Description:** The final commit. The image installs the pinned Bruin CLI, `dlt` / `dbt-core` / `dbt-duckdb` leave `pyproject.toml`, and `loading/` and `dbt/` are deleted. Per the spec's `Ask first` boundary, confirm before deleting.

**Acceptance criteria:**
- [ ] `Dockerfile` installs the pinned CLI so the non-root app user can execute it
- [ ] `dlt`, `dbt-core`, `dbt-duckdb` removed from `pyproject.toml` via `uv remove`
- [ ] `loading/` and `dbt/` deleted
- [ ] No remaining reference to `dbtRunner`, `dlt`, or `/app/loading` in the codebase
- [ ] The baseline is left in place but remains gitignored

**Verification:**
- [ ] `uv run pytest tests -q` passes after the deletions
- [ ] `uv sync` succeeds and `uv run python -c "import dlt"` fails, proving the removal
- [ ] `make local_build && make local_deploy` builds and serves the app
- [ ] `bruin version` inside the container reports the pinned tag
- [ ] The archived spec's Success Criteria are checked off one by one

**Dependencies:** Task 11

**Files likely touched:**
- `Dockerfile`
- `pyproject.toml`
- `uv.lock`
- `loading/` (deleted)
- `dbt/` (deleted)

**Estimated scope:** Medium

---

## Checkpoint G: Complete

- [ ] All Success Criteria in `SPEC.md` met
- [ ] The container builds, serves the app, and carries the pinned Bruin CLI
- [ ] Every task above checked off, with no task left part-done
