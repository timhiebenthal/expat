-- Every configured city has to survive the earnings join.
--
-- job_earnings left-joins the forex rates and used to filter out anything
-- without a rate, so a city whose currency was missing from forex_daily simply
-- disappeared from the dashboard. London vanished exactly that way.
select city_name
from {{ ref("clean__config_cities") }}
where city_name not in (select city_name from {{ ref("job_earnings") }})
