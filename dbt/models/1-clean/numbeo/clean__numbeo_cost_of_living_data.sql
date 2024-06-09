select
    _dlt_id as cost_record_id,
    _dlt_parent_id as city_id,
    category,
    cost as cost_original
from {{ source("numbeo", "cost_of_living__data") }}
