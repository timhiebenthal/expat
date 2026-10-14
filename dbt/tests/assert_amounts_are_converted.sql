-- Costs and salaries have to be convertible. A null here means the currency
-- had no forex rate, and the old code papered over that with a 1.00 fallback
-- that reported GBP figures as if they were EUR.
select city_name, local_currency
from {{ ref("cost_of_living") }}
where cost_eur is null or monthly_activity_cost_eur is null

union all

select city_name, local_currency
from {{ ref("job_earnings") }}
where avg_monthly_gross_salary_eur is null or avg_monthly_net_salary_eur is null
