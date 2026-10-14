-- One-off cutover step: drop the Raw tables dlt created, so the next ingest
-- recreates them in the shape Bruin writes.
--
-- `create+replace` never drops a pre-existing table, so against a warehouse that
-- still holds dlt's tables the ingest keeps the old columns and back-fills them
-- with '-'. Dropping them clears that out; the pipeline rebuilds every one.
--
-- Run against the app's warehouse with the app stopped:
--   export DUCKDB_LOCATION=database/dwh.duckdb
--   duckdb "$DUCKDB_LOCATION" -c "read scripts/drop_dlt_raw.sql"
--   bruin run pipeline --workers 1
--
-- raw_config is app-owned and is deliberately left alone.

drop table if exists raw_numbeo.cost_of_living;
drop table if exists raw_numbeo.cost_of_living__data;
drop table if exists raw_numbeo._dlt_loads;
drop table if exists raw_numbeo._dlt_pipeline_state;
drop table if exists raw_numbeo._dlt_version;

drop table if exists raw_forex.forex_daily;
drop table if exists raw_forex._dlt_loads;
drop table if exists raw_forex._dlt_pipeline_state;
drop table if exists raw_forex._dlt_version;

drop table if exists raw_earnings.job_earnings;
drop table if exists raw_earnings._dlt_loads;
drop table if exists raw_earnings._dlt_pipeline_state;
drop table if exists raw_earnings._dlt_version;
