select 
    city,
    _dlt_load_id,
    _dlt_id as city_id,
from {{ source("numbeo", "cost_of_living") }}