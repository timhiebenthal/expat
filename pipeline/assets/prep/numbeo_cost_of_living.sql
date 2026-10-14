/* @bruin
name: analytics.prep__numbeo_cost_of_living
type: duckdb.sql
connection: duckdb-default

materialization:
  type: table
  strategy: create+replace

depends:
  - analytics.clean__numbeo_cost_of_living
  - analytics.clean__job_earnings
  - analytics.seed_activity_mapping

tags:
  - layer:transform
  - layer:prep
@bruin */
-- Port of the dbt model with the parent/child join removed (the ingest already
-- flattened it). The Cost group mapping keeps its four overrides, and the group
-- column stays collapsed into activity_category rather than being duplicated.
--
-- activity_count is cast to INTEGER because the CSV seed loads it as BIGINT,
-- while dbt's seed was INTEGER and the entity columns keep that type.
with
    currency_per_city as (
        select distinct city_name, local_currency from analytics.clean__job_earnings
    ),

    flattening as (
        select
            city.city_name,
            city.category,
            city.cost_original,
            currency.local_currency,
            round(
                cast(
                    regexp_replace(
                        regexp_replace(
                            regexp_replace(city.cost_original, '[^\d\.]', '', 'g'),
                            '^0+',
                            '',
                            'g'
                        ),
                        ',',
                        '',
                        'g'
                    ) as numeric
                ),
                2
            ) as cost_value
        from analytics.clean__numbeo_cost_of_living as city
        left join currency_per_city as currency using (city_name)
    ),

    map_activities as (
        select
            data.*,
            mapping.activity as activity_name,
            mapping.activity_type,
            case
                when data.category = '1 Bedroom Apartment in City Centre'
                then '1 Room Appart. Center'
                when data.category = '3 Bedroom Apartment in City Centre'
                then '3 Room Appart. Center'
                when data.category = '1 Bedroom Apartment Outside of City Centre'
                then '1 Room Appart. Outside'
                when data.category = '3 Bedroom Apartment Outside of City Centre'
                then '3 Room Appart. Outside'
                else mapping.activity_type
            end as activity_category,
            cast(mapping.activity_count as integer) as monthly_activity_count,
            data.cost_value
            * cast(mapping.activity_count as integer) as monthly_activity_cost
        from flattening as data
        inner join analytics.seed_activity_mapping mapping using (category)
    )

select *
from map_activities
