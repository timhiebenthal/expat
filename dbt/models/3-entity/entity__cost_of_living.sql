with
    cities as (
        select city_name, city_id, activity, cost_original, cost_value, local_currency
        from {{ ref("prep__numbeo_cost_of_living") }} as cost
        where activity is not null  -- only take mapped activities
    ),

    convert_currency as (
        select
            cities.*,
            cities.cost_value * coalesce(forex.conversion_rate, 1.00) as cost_eur
        from cities
        left join
            {{ ref("prep__avg_forex_rate") }} as forex
            on cities.local_currency = forex.from_currency
    )

select *
from convert_currency
