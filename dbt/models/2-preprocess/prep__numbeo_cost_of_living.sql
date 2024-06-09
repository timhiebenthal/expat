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

    map_categories as (
        select
            *,
            case
                when category = 'Meal, Inexpensive Restaurant'
                then 'Restaurant - Basic Meal'
                when category = 'Meal for 2 People, Mid-range Restaurant, Three-course'
                then 'Restaurant - Mid-range Meal for 2'
                when category = 'Domestic Beer (0.5 liter draught)'
                then 'Restaurant - 0.5 Beer Draught'
                when category = 'Coke/Pepsi (0.33 liter bottle)'
                then 'Restaurant - 0.33 Coke'
                when category = 'Water (0.33 liter bottle)'
                then 'Restaurant - 0.33 Water Bottle'
                when category = 'Cappuccino (regular)'
                then 'Restaurant - Cappuccino'
                when category = 'Bottle of Wine (Mid-Range)'
                then 'Supermarket - Bottle of Wine'
                when category = 'Chicken Fillets (1kg)'
                then 'Supermarket - 1kg Chicken Filets'
                when category = 'Banana (1kg)'
                then 'Supermarket - 1kg Banana'
                when category = 'One-way Ticket (Local Transport)'
                then 'Mobility - 1x Public Transport'
                when category = 'Monthly Pass (Regular Price)'
                then 'Mobility - Monthly Public Transport'
                when category = 'Taxi 1km (Normal Tariff)'
                then 'Mobility - 1km Taxi'
                when category = 'Mobile Phone Monthly Plan with Calls and 10GB+ Data'
                then 'Utilities - Mobile Phone Plan'
                when category = 'Internet (60 Mbps or More, Unlimited Data, Cable/ADSL)'
                then 'Utilities - Internet 60Mbps'
                when category = 'Fitness Club, Monthly Fee for 1 Adult'
                then 'Leisure - Monthly Fitness Club'
                when category = 'Cinema, International Release, 1 Seat'
                then 'Leisure - 1x Cinema Ticket'
                when
                    category
                    = 'Preschool (or Kindergarten), Full Day, Private, Monthly for 1 Child'
                then 'Childcare - Monthly Kindergarten'
                when category = 'International Primary School, Yearly for 1 Child'
                then 'Education - Yearly Primary School'
                when category = '1 Pair of Jeans (Levis 501 Or Similar)'
                then 'Clothing - 1x Jeans'
                when category = '1 Summer Dress in a Chain Store (Zara, H&M, ...)'
                then 'Clothing - 1x Summer Dress'
                when category = '1 Pair of Nike Running Shoes (Mid-Range)'
                then 'Clothing - 1x Nike Running Shoes'
                when category = 'Apartment (1 bedroom) in City Centre'
                then 'Housing - 1 Bedroom Apartment'
                when category = 'Apartment (1 bedroom) Outside of Centre'
                then 'Housing - 1 Bedroom Apartment Outside Centre'
                when category = 'Apartment (3 bedrooms) in City Centre'
                then 'Housing - 3 Bedrooms Apartment'
                when category = 'Apartment (3 bedrooms) Outside of Centre'
                then 'Housing - 3 Bedrooms Apartment Outside Centre'
                when
                    category
                    = 'Basic (Electricity, Heating, Cooling, Water, Garbage) for 85m2 Apartment'
                then 'Utilities - Basic for 85m2 Apartment'
                when
                    category
                    = '1 min. of Prepaid Mobile Tariff Local (No Discounts or Plans)'
                then 'Utilities - 1min Mobile Tariff'
                when category = 'Internet (60 Mbps or More, Unlimited Data, Cable/ADSL)'
                then 'Utilities - Internet 60Mbps'
                when category = '1 Pair of Jeans (Levis 501 Or Similar)'
                then 'Clothing - 1x Jeans'
                when category = '1 Summer Dress in a Chain Store (Zara, H&M, ...)'
                then 'Clothing - 1x Summer Dress'
                when category = '1 Pair of Nike Running Shoes (Mid-Range)'
                then 'Clothing - 1x Nike Running Shoes'
                when category = 'Apartment (1 bedroom) in City Centre'
                then 'Housing - 1 Bedroom Apartment'
                when category = 'Apartment (1 bedroom) Outside of Centre'
                then 'Housing - 1 Bedroom Apartment Outside Centre'
                when category = 'Apartment (3 bedrooms) in City Centre'
                then 'Housing - 3 Bedrooms Apartment'
                when category = 'Apartment (3 bedrooms) Outside of Centre'
                then 'Housing - 3 Bedrooms Apartment Outside Centre'
                when
                    category
                    = 'Basic (Electricity, Heating, Cooling, Water, Garbage) for 85m2 Apartment'
                then 'Utilities - Basic for 85m2 Apartment'
                when
                    category
                    = '1 min. of Prepaid Mobile Tariff Local (No Discounts or Plans)'
                then 'Utilities - 1min Mobile Tariff'
                when category = 'Internet (60 Mbps or More, Unlimited Data, Cable/ADSL)'
                then 'Utilities - Internet 60Mbps'
                when category = '1 Pair of Jeans (Levis 501 Or Similar)'
                then 'Clothing - 1x Jeans'
                when category = '1 Summer Dress in a Chain Store (Zara, H&M, ...)'
                then 'Clothing - 1x Summer Dress'
                when category = '1 Pair of Nike Running Shoes (Mid-Range)'
                then 'Clothing - 1x Nike Running Shoes'
                when category = 'Apartment (1 bedroom) in City Centre'
                then 'Rent Housing - 1 Bedroom Apartment'
                when category = 'Apartment (1 bedroom) Outside of Centre'
                then 'Rent Housing - 1 Bedroom Apartment Outside Centre'
                when category = 'Apartment (3 bedrooms) in City Centre'
                then 'Rent Housing - 3 Bedrooms Apartment'
                when category = 'Apartment (3 bedrooms) Outside of Centre'
                then 'Rent Housing - 3 Bedrooms Apartment Outside Centre'
                when
                    category
                    = 'Basic (Electricity, Heating, Cooling, Water, Garbage) for 85m2 Apartment'
                then 'Utilities - Basic for 85m2 Apartment'
                when category = 'Price per Square Meter to Buy Apartment in City Centre'
                then 'Buy Housing - 1sqm Apartment in City Centre'
                when
                    category
                    = 'Price per Square Meter to Buy Apartment Outside of Centre'
                then 'Buy Housing - 1sqm Apartment Outside of City Centre'
            end as activity
        from flattening
    )

select *
from map_categories
