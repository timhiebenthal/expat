select value as city_name from {{ source("cities", "cities") }}
