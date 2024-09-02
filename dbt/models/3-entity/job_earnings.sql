with
    convert_currency as (
        select
            {{
                dbt_utils.generate_surrogate_key(
                    ["city_name", "job_title", "job_experience"]
                )
            }} as entity_id,
            earnings.*,
            (
                earnings.avg_monthly_gross_salary
                * coalesce(forex.conversion_rate, 1.00)
            ) as avg_monthly_gross_salary_eur,
            (
                (earnings.avg_monthly_gross_salary * earnings.net_to_gross_salary_ratio)
                * coalesce(forex.conversion_rate, 1.00)
            ) as avg_monthly_net_salary_eur,
            printf(
                '%s (%d years)', job_title, job_experience
            ) as job_title_experience_short,
        from {{ ref("prep__job_earnings") }} as earnings
        inner join
            {{ ref("prep__avg_forex_rate") }} as forex
            on earnings.local_currency = forex.from_currency
    )

select *
from convert_currency
