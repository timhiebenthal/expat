/* @bruin
name: analytics.core__activity
type: duckdb.sql
connection: duckdb-default

materialization:
  type: table
  strategy: create+replace

depends:
  - analytics.prep__numbeo_cost_of_living

tags:
  - layer:transform
  - layer:core
@bruin */
-- Port of the dbt model. The two CASE arms that both yield true are kept as they
-- are: collapsing them would be a cleanup, not a port.
with
    unique_activities as (
        select distinct
            activity_name,
            activity_type,
            activity_category,
            monthly_activity_count as activity_monthly_default_count,
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
        from analytics.prep__numbeo_cost_of_living
    ),

    add_attributes as (
        select
            *,
            case
                when regexp_matches(activity_name, 'Housing|Education|Child')
                then false
                when category_slug in ('restaurant', 'groceries')
                then true
                else true
            end as is_dynamic_in_dashboard
        from unique_activities
    )

select *
from add_attributes
