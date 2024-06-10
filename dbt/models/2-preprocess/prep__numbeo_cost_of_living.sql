with
    flattening as (
        select
            city.city_name,
            city.city_id,
            data.category,
            data.cost_original,
            config.local_currency,

            round(
                cast(
                    regexp_replace(
                        regexp_replace(
                            regexp_replace(data.cost_original, '[^\d\.]', '', 'g'),  -- Remove all non-numeric characters except the decimal point
                            '^0+',
                            '',
                            'g'  -- Remove leading zeros
                        ),
                        ',',
                        '',
                        'g'
                    ) as numeric
                ),
                2
            ) as cost_value

        from {{ ref("clean__numbeo_cost_of_living") }} as city
        left join {{ ref("clean__numbeo_cost_of_living_data") }} as data using (city_id)
        left join {{ ref("clean__job_earnings") }} as config using (city_name)
    ),

    map_activities as (
        select
            data.*,
            mapping.activity,
            mapping.activity_type,
            case
                when data.category = 'Apartment (1 bedroom) in City Centre'
                then '1 Room Appart. Center'
                when data.category = 'Apartment (3 bedrooms) in City Centre'
                then '3 Room Appart. Center'
                when data.category = 'Apartment (1 bedroom) Outside of Centre'
                then '1 Room Appart. Outside'
                when data.category = 'Apartment (3 bedrooms) Outside of Centre'
                then '3 Room Appart. Outside'
                else mapping.activity_type
            end as activity_category,
            mapping.activity_count as monthly_activity_count,
            data.cost_value * mapping.activity_count as monthly_activity_cost
        from flattening as data
        inner join {{ ref("seed_activity_mapping") }} mapping using (category)
    )

select *
from map_activities
