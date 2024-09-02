with
    clean_job as (
        select
            city_name,
            country_name,
            case
                when jobtitle_and_experience like '% with %'
                then split_part(jobtitle_and_experience, ' with ', 1)
                when regexp_full_match(jobtitle_and_experience, '.*, \d+ years')
                then split_part(jobtitle_and_experience, ', ', 1)
            end as job_title,
            try_cast(
                case
                    when jobtitle_and_experience like '% with %'
                    then
                        regexp_extract(
                            split_part(jobtitle_and_experience, ' with ', 2), '(\d+)'
                        )
                    when regexp_full_match(jobtitle_and_experience, '.*, \d+ years')
                    then regexp_extract(jobtitle_and_experience, '(\d+)')
                end as int
            ) as job_experience,
            local_currency,
            avg_monthly_gross_salary,
            net_to_gross_salary_ratio
        from {{ ref("clean__job_earnings") }}
    ),

    filter_for_jobs_with_data as (

        select clean_job.*
        from clean_job
        inner join
            {{ ref("clean__config_jobs") }} as config
            on clean_job.job_title = config.job_title
            and clean_job.job_experience = config.job_experience
    )

from filter_for_jobs_with_data
