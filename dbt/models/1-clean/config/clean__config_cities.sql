select name as city_name, country as city_country, description as city_description,
from {{ source("config", "cities") }}
