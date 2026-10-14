/* @bruin
name: analytics.clean__numbeo_cost_of_living
type: duckdb.sql
connection: duckdb-default

materialization:
  type: table
  strategy: create+replace

depends:
  - raw_numbeo.cost_of_living

tags:
  - layer:transform
  - layer:clean
@bruin */
-- One model, not two. dlt's parent/child pair is flattened at ingest, so there is
-- no separate __data model to join. city_id was dlt bookkeeping that the app
-- never reads, so it is dropped rather than carried through.
select replace(city, '-', ' ') as city_name, category, cost as cost_original
from raw_numbeo.cost_of_living
