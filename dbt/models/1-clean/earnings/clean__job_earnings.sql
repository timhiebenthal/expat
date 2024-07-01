select
    city as city_name,
    country as country_name,
    jobtitle_and_experience,
    currency as local_currency,
    average_monthly_gross_salary as avg_monthly_gross_salary,
    net_to_gross_salary_ratio
from {{ source("earnings", "job_info") }}
