select
    city as city_name,
    country as country_name,
    job,
    currency as local_currency,
    avg_monthly_gross_salary,
    net_to_gross_salary_ratio
from {{ source("earnings", "job_info") }}
