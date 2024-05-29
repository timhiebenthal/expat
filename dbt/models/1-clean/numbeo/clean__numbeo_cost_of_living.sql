select
    city as city_name,
    _dlt_load_id,
    to_timestamp(cast(_dlt_load_id as numeric)) as _loadet_at,
    _dlt_id as city_id,
from {{ source("numbeo", "cost_of_living") }}
