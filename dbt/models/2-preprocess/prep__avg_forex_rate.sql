select
    from_currency, to_currency, round(cast(avg(close) as numeric), 3) as conversion_rate
from {{ ref("clean__forex_forex_daily") }}
group by from_currency, to_currency
