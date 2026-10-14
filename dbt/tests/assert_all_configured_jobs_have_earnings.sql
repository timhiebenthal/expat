-- Every configured job has to end up in job_earnings.
--
-- assert_all_cities_have_earnings only catches a total loss: with more than one
-- job configured, the surviving jobs keep the cities present while a job that
-- produced nothing disappears on its own. prep__job_earnings matches on the
-- parsed job title, so a reworded one drops silently.
select config.job_title, config.job_experience
from {{ ref("clean__config_jobs") }} as config
where not exists (
    select 1
    from {{ ref("prep__job_earnings") }} as earnings
    where
        earnings.job_title = config.job_title
        and earnings.job_experience = config.job_experience
)
