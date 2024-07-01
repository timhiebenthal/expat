with
    clean_job as (
        select
            city_name,
            country_name,
            split_part(jobtitle_and_experience, ' with ', 1) as job_title,
            try_cast(
                regexp_extract(
                    split_part(jobtitle_and_experience, ' with ', 2), '(\d+)'
                ) as int
            ) as job_experience,
            local_currency,
            avg_monthly_gross_salary,
            net_to_gross_salary_ratio
        from {{ ref("clean__job_earnings") }}
    )

from clean_job
