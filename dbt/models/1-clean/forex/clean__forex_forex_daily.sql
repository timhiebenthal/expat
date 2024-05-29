select
    _dlt_id as forex_record_id,
    _dlt_load_id,
    to_timestamp(cast(_dlt_load_id as numeric)) as _loadet_at,
    date,
    open,
    high,
    low,
    close,
    from_currency,
    to_currency
from {{ source("forex", "forex_daily") }}
