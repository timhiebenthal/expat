/* @bruin
name: analytics.core__job_earnings
type: duckdb.sql
connection: duckdb-default

materialization:
  type: table
  strategy: create+replace

depends:
  - analytics.prep__job_earnings
  - analytics.prep__avg_forex_rate

tags:
  - layer:transform
  - layer:core
@bruin */

-- entity_id reproduces dbt_utils.generate_surrogate_key exactly: md5 over the
-- pipe-joined, null-coalesced, cast-to-TEXT fields. It is checked against the
-- baseline, so the expression is copied from the compiled dbt SQL rather than
-- reimplemented.
with
    convert_currency as (
        select
            md5(
                cast(
                    coalesce(cast(city_name as TEXT), '_dbt_utils_surrogate_key_null_')
                    || '-'
                    || coalesce(cast(job_title as TEXT), '_dbt_utils_surrogate_key_null_')
                    || '-'
                    || coalesce(cast(job_experience as TEXT), '_dbt_utils_surrogate_key_null_')
                    as TEXT
                )
            ) as entity_id,
            earnings.*,
            round(
                earnings.avg_monthly_gross_salary / forex.conversion_rate, 2
            ) as avg_monthly_gross_salary_eur,
            round(
                (earnings.avg_monthly_gross_salary * earnings.net_to_gross_salary_ratio)
                / forex.conversion_rate,
                2
            ) as avg_monthly_net_salary_eur,
            printf('%s (%d years)', job_title, job_experience)
                as job_title_experience_short
        from analytics.prep__job_earnings as earnings
        left join analytics.prep__avg_forex_rate as forex
            on earnings.local_currency = forex.from_currency
    )

select *
from convert_currency
