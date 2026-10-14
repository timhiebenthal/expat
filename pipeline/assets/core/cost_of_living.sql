/* @bruin
name: analytics.core__cost_of_living
type: duckdb.sql
connection: duckdb-default

materialization:
  type: table
  strategy: create+replace

depends:
  - analytics.prep__numbeo_cost_of_living
  - analytics.prep__avg_forex_rate

tags:
  - layer:transform
  - layer:core

# assert_amounts_are_converted, as column checks.
columns:
  - name: cost_eur
    type: double
    checks:
      - name: not_null
  - name: monthly_activity_cost_eur
    type: double
    checks:
      - name: not_null

custom_checks:
  # assert_all_cities_have_cost_of_living. prep inner-joins the scraped labels
  # against the seed mapping, so a city whose labels stop matching goes quiet.
  - name: every configured city has cost of living
    query: |
      select count(*)
      from analytics.clean__config_cities
      where city_name not in (select city_name from analytics.core__cost_of_living)
    value: 0
@bruin */
-- Port of the dbt model, minus dlt's city_id (unread by the app, and no longer
-- produced now that numbeo is flat). category_slug inlines the slugify macro.
with
    cities as (
        select
            city_name,
            activity_name,
            activity_type,
            activity_category,
            monthly_activity_count,
            monthly_activity_cost,
            cost_value,
            local_currency
        from analytics.prep__numbeo_cost_of_living as cost
        where activity_name is not null
    ),

    convert_currency as (
        select
            cities.*,
            round(cities.cost_value / forex.conversion_rate, 2) as cost_eur,
            round(
                cities.monthly_activity_cost / forex.conversion_rate, 2
            ) as monthly_activity_cost_eur,
            regexp_replace(
                regexp_replace(
                    regexp_replace(
                        regexp_replace(lower(activity_category), '[ -]+', '_'),
                        '^[0-9]',
                        concat('_', substr(activity_category, 1, 1))
                    ),
                    '[^a-z0-9_]+',
                    ''
                ),
                '[ .]+',
                '_'
            ) as category_slug
        from cities
        left join
            analytics.prep__avg_forex_rate as forex
            on cities.local_currency = forex.from_currency
    )

select *
from convert_currency
