with
    convert_currency as (
        select
            {{
                dbt_utils.generate_surrogate_key(
                    ["city_name", "job_title", "job_experience"]
                )
            }} as entity_id,
            earnings.*,
            round(
                earnings.avg_monthly_gross_salary
                / coalesce(forex.conversion_rate, 1.00),
                2
            ) as avg_monthly_gross_salary_eur,
            round(
                (earnings.avg_monthly_gross_salary * earnings.net_to_gross_salary_ratio)
                / coalesce(forex.conversion_rate, 1.00),
                2
            ) as avg_monthly_net_salary_eur,
            printf(
                '%s (%d years)', job_title, job_experience
            ) as job_title_experience_short,
        from {{ ref("prep__job_earnings") }} as earnings
        left join
            {{ ref("prep__avg_forex_rate") }} as forex
            on earnings.local_currency = forex.from_currency
        where forex.conversion_rate is not null or earnings.local_currency = 'EUR'  -- hardcoded base currency for now.
    )

select *
from convert_currency
