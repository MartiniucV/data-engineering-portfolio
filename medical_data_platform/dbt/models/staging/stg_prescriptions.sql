{{ config(materialized='view') }}

with source as (
    select * from {{ source('raw', 'prescriptions') }}
)

select
    prescription_id,
    appointment_id,
    doctor_id,
    patient_id,
    medication_name,
    dosage,
    frequency,
    least(greatest(coalesce(duration_days::integer, 7), 1), 365) as duration_days,
    prescribed_at::timestamptz                                    as prescribed_at,
    prescribed_at::date                                           as prescribed_date,
    coalesce(is_chronic::boolean, false)                          as is_chronic,
    now()                                                         as _dbt_loaded_at
from source
where prescription_id is not null
