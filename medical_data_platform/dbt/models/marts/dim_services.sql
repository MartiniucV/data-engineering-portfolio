{{ config(materialized='table', schema='analytics') }}

select
    service_id,
    service_code,
    service_name,
    category,
    base_price,
    duration_minutes,
    profitability_margin,
    reimbursement_pct,
    round(base_price * profitability_margin, 2)          as expected_margin_amount,
    round(base_price * reimbursement_pct, 2)             as expected_reimbursement,
    is_active,
    now()                                               as dbt_updated_at
from {{ ref('stg_services') }}
