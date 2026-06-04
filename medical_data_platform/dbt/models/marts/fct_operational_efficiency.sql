{{ config(materialized='table', schema='analytics') }}

-- Aggregated at month level for performance on 2M-row datasets
select
    date_trunc('month', appointment_date)::date  as ops_date,
    appointment_year                              as ops_year,
    appointment_month                             as ops_month,
    clinic_id,
    clinic_city,
    specialty,
    sum(total_appointments)     as total_appointments,
    sum(completed)              as completed,
    sum(cancelled)              as cancelled,
    sum(no_shows)               as no_shows,
    sum(rescheduled)            as rescheduled,
    max(active_doctors)         as active_doctors,
    sum(unique_patients)        as unique_patients,
    round(avg(avg_wait_minutes)::numeric, 1)   as avg_wait_minutes,
    max(max_wait_minutes)                      as max_wait_minutes,
    round(avg(avg_consult_minutes)::numeric, 1) as avg_consult_minutes,
    round(
        sum(completed)::numeric / nullif(sum(total_appointments), 0), 4
    )                           as completion_rate,
    round(
        sum(cancelled)::numeric / nullif(sum(total_appointments), 0), 4
    )                           as cancellation_rate,
    round(
        sum(no_shows)::numeric  / nullif(sum(total_appointments), 0), 4
    )                           as no_show_rate,
    sum(daily_revenue)          as daily_revenue,
    null::numeric               as ma7_completion_rate,
    null::numeric               as ma7_no_show_rate,
    null::numeric               as ma7_avg_wait,
    now()                       as dbt_updated_at
from {{ ref('int_operational_metrics') }}
group by 1, 2, 3, 4, 5, 6
