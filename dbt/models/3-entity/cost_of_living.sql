with
    cities as (
        select
            city_name,
            city_id,
            activity_name,
            activity_type,
            activity_category,
            monthly_activity_count,
            monthly_activity_cost,
            cost_value,
            local_currency
        from {{ ref("prep__numbeo_cost_of_living") }} as cost
        where activity_name is not null  -- only take mapped activities
    ),

    convert_currency as (
        select
            cities.*,
            round(
                cities.cost_value / coalesce(forex.conversion_rate, 1.00), 2
            ) as cost_eur,
            round(
                cities.monthly_activity_cost / coalesce(forex.conversion_rate, 1.00), 2
            ) as monthly_activity_cost_eur,
            {{ slugify_column_values("activity_category") }} as category_slug
        from cities
        left join
            {{ ref("prep__avg_forex_rate") }} as forex
            on cities.local_currency = forex.from_currency
    )

select *
from convert_currency
