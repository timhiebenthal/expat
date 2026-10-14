/* @bruin
name: analytics.clean__forex_forex_daily
type: duckdb.sql
connection: duckdb-default

materialization:
  type: table
  strategy: create+replace

depends:
  - raw_forex.forex_daily

tags:
  - layer:transform
  - layer:clean
@bruin */

-- Faithful port of the dbt model minus the dlt metadata it used to carry.
-- forex_record_id / _dlt_load_id / _loadet_at were dlt bookkeeping, unused
-- downstream, so the Bruin ingest does not reproduce them and they are dropped
-- here. Parity is gated on the entity tables, not on this one.
select
    date,
    open,
    high,
    low,
    close,
    from_currency,
    to_currency
from raw_forex.forex_daily
