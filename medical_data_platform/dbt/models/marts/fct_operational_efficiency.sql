{{ config(materialized='table', schema='analytics') }}

select
    appointment_date    as ops_date,
    appointment_year    as ops_year,
    appointment_month   as ops_month,
    clinic_id,
    clinic_city,
    specialty,
    total_appointments,
    completed,
    cancelled,
    no_shows,
    rescheduled,
    active_doctors,
    unique_patients,
    avg_wait_minutes,
    max_wait_minutes,
    avg_consult_minutes,
    completion_rate,
    cancellation_rate,
    no_show_rate,
    daily_revenue,

    -- 7-day moving averages
    round(
        avg(completion_rate)   over (partition by clinic_id, specialty order by appointment_date rows between 6 preceding and current row),
        4
    )                   as ma7_completion_rate,
    round(
        avg(no_show_rate) over (partition by clinic_id, specialty order by appointment_date rows between 6 preceding and current row),
        4
    )                   as ma7_no_show_rate,
    round(
        avg(avg_wait_minutes) over (partition by clinic_id, specialty order by appointment_date rows between 6 preceding and current row),
        1
    )                   as ma7_avg_wait,

    now()               as dbt_updated_at
from {{ ref('int_operational_metrics') }}
