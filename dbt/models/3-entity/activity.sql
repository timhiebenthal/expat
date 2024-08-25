with
    unique_activities as (
        select distinct
            activity_name,
            activity_type,
            activity_category,
            monthly_activity_count as activity_monthly_default_count,
            {{ slugify_column_values("activity_category") }} as category_slug
        from {{ ref("prep__numbeo_cost_of_living") }}
    ),

    add_attributes as (
        select
            *,
            case
                when category_slug in ('restaurant', 'groceries') then true else false
            end as is_dynamic_in_dashboard,
        from unique_activities
    )

select *
from add_attributes
