-- Every configured city has to survive the numbeo join too.
--
-- prep__numbeo_cost_of_living inner-joins the scraped categories against
-- seed_activity_mapping, so a city whose labels no longer match disappears
-- without a word.
select city_name
from {{ ref("clean__config_cities") }}
where city_name not in (select city_name from {{ ref("cost_of_living") }})
