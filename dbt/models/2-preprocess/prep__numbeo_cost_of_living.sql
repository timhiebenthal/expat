select
*
from {{ ref("clean__numbeo_cost_of_living") }} as cities
left join {{ ref("clean__numbeo_cost_of_living_data") }} as data
    using (city_id)