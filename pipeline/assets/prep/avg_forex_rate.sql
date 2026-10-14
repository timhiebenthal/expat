/* @bruin
name: analytics.prep__avg_forex_rate
type: duckdb.sql
connection: duckdb-default

materialization:
  type: table
  strategy: create+replace

depends:
  - analytics.clean__forex_forex_daily

tags:
  - layer:transform
  - layer:prep
@bruin */
-- Verbatim port of the dbt model. It reads only from_currency, to_currency and
-- close, so dropping dlt's columns from clean does not move its output.
select
    from_currency, to_currency, round(cast(avg(close) as numeric), 3) as conversion_rate
from analytics.clean__forex_forex_daily
group by from_currency, to_currency
