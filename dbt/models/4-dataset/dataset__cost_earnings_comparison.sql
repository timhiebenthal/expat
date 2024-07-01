with
    earnings as (

        select
            city_name,
            country_name,
            job_title,
            job_experience,
            job_title_experience_short,
            avg_monthly_gross_salary_eur,
            avg_monthly_net_salary_eur
        from {{ ref("entity__job_earnings") }}

    ),

    pivot_expenses as (
        pivot {{ ref("entity__cost_of_living") }} on category_slug
        using sum(monthly_activity_cost_eur)
        group by city_name
    ),

    cost as (

        select
            city_name,
            _1_roomappart_center as expense_1_roomappart_center,
            _1_roomappart_outside as expense_1_roomappart_outside,
            _3_roomappart_center as expense_3_roomappart_center,
            _3_roomappart_outside as expense_3_roomappart_outside,
            {# buy_housing as expense_buy_housing, -- needs more work #}
            childcare as expense_childcare,
            clothing as expense_clothing,
            education as expense_education,
            groceries as expense_groceries,
            leisure as expense_leisure,
            mobility as expense_mobility,
            restaurant as expense_restaurant,
            utilities as expense_utilities,

        from pivot_expenses
    ),

    flatten as (select * from earnings left join cost using (city_name))

select *
from flatten
