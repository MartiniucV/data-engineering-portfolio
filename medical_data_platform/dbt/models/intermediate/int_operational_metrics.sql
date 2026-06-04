{{ config(materialized='view') }}

with appointments as (
    select * from {{ ref('int_appointment_metrics') }}
),

daily_ops as (
    select
        appointment_date,
        appointment_year,
        appointment_month,
        clinic_id,
        clinic_city,
        specialty,

        count(appointment_id)                                   as total_appointments,
        count(appointment_id) filter (where is_completed)       as completed,
        count(appointment_id) filter (where is_cancelled)       as cancelled,
        count(appointment_id) filter (where is_no_show)         as no_shows,
        count(appointment_id) filter (where is_rescheduled)     as rescheduled,
        count(distinct doctor_id)                               as active_doctors,
        count(distinct patient_id)                              as unique_patients,

        round(avg(waiting_time_minutes)::numeric, 1)            as avg_wait_minutes,
        max(waiting_time_minutes)                               as max_wait_minutes,
        round(avg(consultation_duration_minutes)::numeric, 1)   as avg_consult_minutes,

        round(
            count(appointment_id) filter (where is_completed)::numeric
            / nullif(count(appointment_id), 0), 4
        )                                                       as completion_rate,
        round(
            count(appointment_id) filter (where is_cancelled)::numeric
            / nullif(count(appointment_id), 0), 4
        )                                                       as cancellation_rate,
        round(
            count(appointment_id) filter (where is_no_show)::numeric
            / nullif(count(appointment_id), 0), 4
        )                                                       as no_show_rate,

        sum(net_revenue)                                        as daily_revenue

    from appointments
    group by 1, 2, 3, 4, 5, 6
)

select * from daily_ops
