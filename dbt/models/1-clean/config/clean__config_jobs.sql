select job_title, years_experience as job_experience from {{ source("config", "jobs") }}
