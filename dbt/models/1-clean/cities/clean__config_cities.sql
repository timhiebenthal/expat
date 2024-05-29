select name as city_name, country, currency from {{ source("cities", "cities") }}
