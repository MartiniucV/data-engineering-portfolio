{{ config(materialized='view') }}

with source as (
    select * from {{ source('raw', 'services') }}
)

select
    service_id,
    code                                                as service_code,
    name                                                as service_name,
    category,
    greatest(base_price::numeric(10,2), 0)             as base_price,
    coalesce(duration_minutes::integer, 30)             as duration_minutes,
    least(greatest(profitability_margin::numeric(5,4), 0), 1) as profitability_margin,
    least(greatest(reimbursement_pct::numeric(5,4), 0), 1)    as reimbursement_pct,
    is_active::boolean                                  as is_active,
    now()                                               as _dbt_loaded_at
from source
where service_id is not null
