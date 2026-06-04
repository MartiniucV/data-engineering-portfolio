{{ config(materialized='view') }}

with source as (
    select * from {{ source('raw', 'appointments') }}
),

cleaned as (
    select
        appointment_id,
        patient_id,
        doctor_id,
        service_id,
        clinic_id,
        specialty,
        scheduled_at::timestamptz                                           as scheduled_at,
        actual_start::timestamptz                                           as actual_start,
        actual_end::timestamptz                                             as actual_end,
        status,
        least(greatest(coalesce(waiting_time_minutes::integer, 0), 0), 300)
                                                                            as waiting_time_minutes,
        coalesce(consultation_duration_minutes::integer, 0)                 as consultation_duration_minutes,
        channel,
        urgency_level,
        referral_source,
        cancellation_reason,
        greatest(coalesce(actual_price::numeric(10,2), 0), 0)              as actual_price,
        coalesce(discount_pct::numeric(5,4), 0)                            as discount_pct,
        least(greatest(rating::numeric(3,1), 1.0), 5.0)                   as rating,
        notes,

        -- Time dimensions
        scheduled_at::date                                                  as appointment_date,
        date_part('year', scheduled_at)::integer                           as appointment_year,
        date_part('month', scheduled_at)::integer                          as appointment_month,
        date_part('quarter', scheduled_at)::integer                        as appointment_quarter,
        to_char(scheduled_at, 'Day')                                       as day_of_week,
        date_part('hour', scheduled_at)::integer                           as appointment_hour,
        date_part('isodow', scheduled_at) >= 6                             as is_weekend,

        -- Status flags
        (status = 'completed')                                             as is_completed,
        (status = 'cancelled')                                             as is_cancelled,
        (status = 'no_show')                                               as is_no_show,
        (status = 'rescheduled')                                           as is_rescheduled,

        now()                                                               as _dbt_loaded_at
    from source
    where appointment_id is not null
      and status in ('completed','cancelled','no_show','rescheduled')
)

select * from cleaned
