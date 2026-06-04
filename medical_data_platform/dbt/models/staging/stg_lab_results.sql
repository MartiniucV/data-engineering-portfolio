{{ config(materialized='view') }}

with source as (
    select * from {{ source('raw', 'lab_results') }}
)

select
    lab_result_id,
    appointment_id,
    patient_id,
    test_name,
    value::numeric(12,3)                            as value,
    unit,
    reference_range_low::numeric(12,3)              as reference_range_low,
    reference_range_high::numeric(12,3)             as reference_range_high,
    coalesce(is_abnormal::boolean, false)           as is_abnormal,
    collected_at::timestamptz                       as collected_at,
    result_at::timestamptz                          as result_at,
    collected_at::date                              as collected_date,

    -- Turnaround hours
    round(
        extract(epoch from (result_at::timestamptz - collected_at::timestamptz)) / 3600.0,
        1
    )                                               as turnaround_hours,

    now()                                           as _dbt_loaded_at
from source
where lab_result_id is not null
  and value is not null
