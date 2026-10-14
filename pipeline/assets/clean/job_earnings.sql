/* @bruin
name: analytics.clean__job_earnings
type: duckdb.sql
connection: duckdb-default

materialization:
  type: table
  strategy: create+replace

depends:
  - raw_earnings.job_earnings

tags:
  - layer:transform
  - layer:clean
@bruin */
-- Verbatim port, minus dlt's _dlt_load_id / _dlt_id: the new ingest does not
-- write them and nothing downstream reads them.
select
    city as city_name,
    country as country_name,
    jobtitle_and_experience,
    currency as local_currency,
    average_monthly_gross_salary as avg_monthly_gross_salary,
    net_to_gross_salary_ratio
from raw_earnings.job_earnings
