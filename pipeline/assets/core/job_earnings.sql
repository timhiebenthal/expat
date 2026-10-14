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

# assert_amounts_are_converted, as column checks: a null EUR amount means the
# currency had no forex rate.
columns:
  - name: avg_monthly_gross_salary_eur
    type: double
    checks:
      - name: not_null
  - name: avg_monthly_net_salary_eur
    type: double
    checks:
      - name: not_null

custom_checks:
  # assert_all_cities_have_earnings. job_earnings left-joins the forex rates, so
  # a city whose currency is missing from forex_daily just disappears. London did.
  - name: every configured city has earnings
    query: |
      select count(*)
      from analytics.clean__config_cities
      where city_name not in (select city_name from analytics.core__job_earnings)
    value: 0
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
                    coalesce(cast(city_name as text), '_dbt_utils_surrogate_key_null_')
                    || '-'
                    || coalesce(
                        cast(job_title as text), '_dbt_utils_surrogate_key_null_'
                    )
                    || '-'
                    || coalesce(
                        cast(job_experience as text), '_dbt_utils_surrogate_key_null_'
                    ) as text
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
            printf(
                '%s (%d years)', job_title, job_experience
            ) as job_title_experience_short
        from analytics.prep__job_earnings as earnings
        left join
            analytics.prep__avg_forex_rate as forex
            on earnings.local_currency = forex.from_currency
    )

select *
from convert_currency
