select name as city_name from {{ source("cities", "cities") }}
