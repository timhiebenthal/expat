/* @bruin
name: analytics.clean__config_jobs
type: duckdb.sql
connection: duckdb-default

materialization:
  type: table
  strategy: create+replace

tags:
  - layer:transform
  - layer:clean
@bruin */

-- raw_config is app-owned and not a Bruin asset, so there is nothing to depend
-- on here; it always exists by the time a run starts.
select job_title, years_experience as job_experience
from raw_config.jobs
