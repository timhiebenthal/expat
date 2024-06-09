with
    cities as (
        select
            city_name,
            city_id,
            activity,
            activity_type,
            activity_category,
            monthly_activity_count,
            monthly_activity_cost,
            cost_value,
            local_currency
        from {{ ref("prep__numbeo_cost_of_living") }} as cost
        where activity is not null  -- only take mapped activities
    ),

    convert_currency as (
        select
            cities.*,
            cities.cost_value * coalesce(forex.conversion_rate, 1.00) as cost_eur,
            cities.monthly_activity_cost
            * coalesce(forex.conversion_rate, 1.00) as monthly_activity_cost_eur,
            {{ slugify_column_values("cities.activity_category") }} as category_slug
        from cities
        left join
            {{ ref("prep__avg_forex_rate") }} as forex
            on cities.local_currency = forex.from_currency
    ),

    pivot_values as (
        pivot convert_currency on activity using sum(cost_eur) group by city_name
    )

select *
from convert_currency
