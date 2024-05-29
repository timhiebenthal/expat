select
    _dlt_id as cost_record_id,
    _dlt_parent_id as city_id,
    category,
    cost,
    right(cost, 1) as currency,
    ROUND(CAST(REGEXP_REPLACE(
        REGEXP_REPLACE(cost, '([\$€£¥₹₩])', '', 'g'),
            ',',
            '',
            'g'
        ) AS NUMERIC),2) as cost_eur
from {{ source('numbeo', 'cost_of_living__data') }}