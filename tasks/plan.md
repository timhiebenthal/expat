# Implementation Plan: Migrate the pipeline from dlt + dbt to Bruin

## Overview

Port a 13-model dlt + dbt pipeline to Bruin, ending with dlt and dbt deleted and the Streamlit app triggering `bruin run` instead of shelling out to three Python loaders and `dbt build`. Success is data parity with the current output, not new features. The full contract is `SPEC.md`; the approved capability map is `ingest` / `transform` / `quality` / `app-trigger` / `cutover`, with `oracle` as a precondition rather than a module.

## Architecture Decisions

- **Capture the baseline before anything else.** Three of the four inputs are non-deterministic across runs, so parity is only meaningful against frozen inputs. Once dlt stops writing `raw_*`, the inputs cannot be reconstructed. This is the one irreversible step, so it goes first.
- **Parity runs against a separate file.** `DUCKDB_LOCATION` points at `baseline/dwh.duckdb`, which the app never opens. A writer holds an exclusive DuckDB lock - even read-only opens are refused - so this is what keeps the app from having to be stopped.
- **Two parity gates.** `bruin data-diff --full` covers schema, row counts and statistics but never compares rows. Bidirectional `EXCEPT ALL` provides exact row equality, which is required because row loss is this project's recurring failure.
- **Baseline tables are renamed to the target names** (`analytics.job_earnings` becomes `baseline.core__job_earnings`) so comparison is a direct `EXCEPT ALL` with no name translation.
- **`ingest` and `transform` are separate modules with a named contract.** The `raw_*` table shapes are `ingest`'s interface; `transform` consumes them. Flattening numbeo at load removes the dlt parent/child split and one model with it.
- **Pyramid order: prove the risky mechanics first.** Baseline capture and "does Bruin run against DuckDB at all" both fail fast, so they precede any model porting.

## Dependency Graph

```
oracle   baseline copy (raw_* frozen + baseline.* + manifest)   <- irreversible, first
   |
ingest   raw_numbeo.cost_of_living   raw_earnings.job_earnings   raw_forex.forex_daily
   |              |                             |                        |
transform         |                             |                        |
   |     clean__numbeo_cost_of_living   clean__job_earnings   clean__forex_forex_daily
   |              |                             |                        |
   |              |                    prep__job_earnings     prep__avg_forex_rate
   |              |                             |                        |
   |     prep__numbeo_cost_of_living  <-- currency --+                    |
   |              |                                 |                    |
   |              +--> core__activity               +--> core__job_earnings
   |              |
   |              +--> core__cost_of_living <-------------- rates --------+
   |
   +-- clean__config_cities / clean__config_jobs  <- raw_config.* (app-owned, frozen in the baseline copy)

quality      checks attach to the assets above
app-trigger  Streamlit runs `bruin run`; the three app queries are renamed
cutover      delete dlt/dbt, drop dependencies, remove the baseline
```

Consequence for ordering: `core__cost_of_living` needs currency and FX rates, so the forex and earnings paths cannot be deferred behind the numbeo path. That is why Phase 2 comes before Phase 3.

## Task List

### Phase 0: Foundations (fail-fast, sequential)
- [x] Task 1 `[oracle]` Branch and capture the baseline
- [x] Task 2 `[ingest]` Bruin skeleton proven against DuckDB

### Checkpoint A
- [x] Baseline is captured, verified and untracked
- [x] `bruin validate` and `bruin run` both succeed against the baseline copy

### Phase 1: Shared Python (three disjoint streams, parallelizable)
- [x] Task 3 `[ingest]` Extract `pipeline/lib/numbeo.py`
- [x] Task 4 `[ingest]` Extract `pipeline/lib/forex.py`
- [x] Task 5 `[ingest]` Extract `pipeline/lib/earnings.py`

### Checkpoint B
- [x] `uv run pytest tests` green with imports re-pointed
- [x] No network access anywhere under `pipeline/lib/`

### Phase 2: Forex and earnings paths (app-visible: `core__job_earnings`)
- [x] Task 6 `[ingest]` Forex path end to end
- [x] Task 7 `[ingest]` Earnings path end to end

### Checkpoint C
- [x] `core__job_earnings` matches the baseline exactly
- [x] Forex and earnings Raw tables have the grain the entity tables expect (column parity is not required)

### Phase 3: Cost path (app-visible: `core__cost_of_living`, `core__activity`)
- [ ] Task 8 `[ingest]` Numbeo path end to end, flattened
- [ ] Task 9 `[transform]` Cost and activity core models

### Checkpoint D
- [ ] Every table the app reads matches the baseline exactly
- [ ] Both parity gates pass for all of them

### Phase 4: Quality
- [ ] Task 10 `[quality]` Port the four checks

### Checkpoint E
- [ ] Each check has been observed failing on deliberately broken input

### Phase 5: App trigger
- [ ] Task 11 `[app-trigger]` Streamlit runs the Bruin pipeline

### Checkpoint F
- [ ] "Submit Cities" runs the pipeline end to end and the page renders

### Phase 6: Cutover
- [ ] Task 12 `[cutover]` Remove dlt and dbt

### Checkpoint G: Complete
- [ ] All Success Criteria in `SPEC.md` met
- [ ] The container builds, serves the app, and carries a pinned Bruin CLI

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Baseline captured too late or from a stale `analytics.*`, making parity meaningless | High | Task 1 is first and runs a final `dbt build` before copying; the manifest records row counts so a stale capture is visible |
| `${DUCKDB_LOCATION}` unset fails silently into a literal path | Medium | Task 2 deliberately runs once without it to observe the failure mode, and every command in `SPEC.md` exports it first |
| Porting drifts into "improving" models, so parity is never reached | High | Parity is the only acceptance criterion; any change to output is a defect until parity passes |
| `data-diff` passing while rows are missing | High | Bidirectional `EXCEPT ALL` is a required second gate, not optional |
| Bruin and a running app contending for the DuckDB file | Medium | Parity always points at the baseline copy, never `database/dwh.duckdb` |
| Python assets pulling dependencies from the repo root unexpectedly | Low | Task 2 confirms asset execution before any asset depends on third-party libraries |
| Renaming core models breaks the app's queries | Medium | Isolated in Task 11 with the page render as its verification |

## Parallelization Opportunities

Phase 1 is three genuinely independent streams with disjoint files: `pipeline/lib/numbeo.py` + `tests/test_costofliving.py`, `pipeline/lib/forex.py` + `tests/test_forex.py`, `pipeline/lib/earnings.py` + `tests/test_llm_earnings.py`. No file appears in two streams.

Tasks 6 and 7 touch disjoint asset and model files but both depend on Task 2, so they can run in parallel once Checkpoint B passes.

Everything else is sequential: the phases share `pipeline/` configuration, and Checkpoints C and D are the same two gates run over different tables.

## Open Questions

None outstanding - all five from the spec were settled. Anything discovered during `transform` that contradicts `SPEC.md` should be raised before porting continues rather than worked around.
