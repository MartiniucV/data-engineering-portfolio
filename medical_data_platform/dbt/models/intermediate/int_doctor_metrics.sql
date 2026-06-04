{{ config(materialized='view') }}

with appointments as (
    select * from {{ ref('int_appointment_metrics') }}
),

doctors as (
    select * from {{ ref('stg_doctors') }}
),

aggregated as (
    select
        doctor_id,
        count(appointment_id)                                           as total_appointments,
        count(appointment_id) filter (where is_completed)              as completed_appointments,
        count(appointment_id) filter (where is_cancelled)              as cancelled_appointments,
        count(appointment_id) filter (where is_no_show)                as no_show_appointments,
        count(appointment_id) filter (where is_rescheduled)            as rescheduled_appointments,

        round(avg(rating) filter (where rating is not null), 2)        as avg_patient_rating,
        round(avg(waiting_time_minutes)::numeric, 1)                   as avg_wait_minutes,
        round(avg(consultation_duration_minutes)::numeric, 1)          as avg_consult_minutes,

        sum(net_revenue)                                               as total_revenue,
        round(avg(net_revenue) filter (where is_completed), 2)        as avg_revenue_per_appt,
        sum(net_revenue) filter (where appointment_year = 2023)        as revenue_2023,
        sum(net_revenue) filter (where appointment_year = 2024)        as revenue_2024,

        count(distinct patient_id)                                     as unique_patients,
        count(distinct appointment_date)                               as active_days,
        round(
            count(appointment_id) filter (where is_completed)::numeric
            / nullif(count(appointment_id), 0), 4
        )                                                              as completion_rate,
        round(
            count(appointment_id) filter (where is_no_show)::numeric
            / nullif(count(appointment_id), 0), 4
        )                                                              as no_show_rate

    from appointments
    group by doctor_id
),

final as (
    select
        d.doctor_id,
        d.full_name,
        d.specialty,
        d.clinic_id,
        d.seniority_band,
        d.years_experience,
        d.hire_date,
        d.consultation_price,
        d.rating                                        as profile_rating,
        d.monthly_salary,
        d.performance_score,
        d.is_active,
        coalesce(a.total_appointments, 0)               as total_appointments,
        coalesce(a.completed_appointments, 0)           as completed_appointments,
        coalesce(a.cancelled_appointments, 0)           as cancelled_appointments,
        coalesce(a.no_show_appointments, 0)             as no_show_appointments,
        a.avg_patient_rating,
        a.avg_wait_minutes,
        a.avg_consult_minutes,
        coalesce(a.total_revenue, 0)                    as total_revenue,
        a.avg_revenue_per_appt,
        coalesce(a.revenue_2023, 0)                     as revenue_2023,
        coalesce(a.revenue_2024, 0)                     as revenue_2024,
        coalesce(a.unique_patients, 0)                  as unique_patients,
        coalesce(a.active_days, 0)                      as active_days,
        coalesce(a.completion_rate, 0)                  as completion_rate,
        coalesce(a.no_show_rate, 0)                     as no_show_rate,

        -- Synthetic performance tier
        case
            when coalesce(a.completion_rate, 0) >= 0.80 and a.avg_patient_rating >= 4.5
                then 'Top Performer'
            when coalesce(a.completion_rate, 0) >= 0.70 and a.avg_patient_rating >= 4.0
                then 'Strong Performer'
            when coalesce(a.completion_rate, 0) >= 0.60
                then 'Solid Performer'
            else 'Needs Improvement'
        end                                             as performance_tier

    from doctors d
    left join aggregated a on d.doctor_id = a.doctor_id
)

select * from final
