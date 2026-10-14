/* @bruin
name: analytics.clean__config_cities
type: duckdb.sql
connection: duckdb-default

materialization:
  type: table
  strategy: create+replace

tags:
  - layer:transform
  - layer:clean
@bruin */

-- raw_config is app-owned and not a Bruin asset, so there is nothing to depend on.
select name as city_name, country as city_country
from raw_config.cities
