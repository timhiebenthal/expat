with
    earnings as (

        select
            city_name,
            country_name,
            job_title,
            job_experience,
            avg_monthly_gross_salary_eur,
            avg_monthly_net_salary_eur
        from {{ ref("entity__job_earnings") }}

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
        from {{ ref("entity__cost_of_living") }}

    ),

    flatten as (select * from earnings left join cost using (city_name))

select *
from flatten
