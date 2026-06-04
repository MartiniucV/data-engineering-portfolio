{{ config(materialized='view') }}

with appointments as (
    select * from {{ ref('stg_appointments') }}
),

payments as (
    select * from {{ ref('stg_payments') }}
),

doctors as (
    select doctor_id, specialty, clinic_id, full_name as doctor_name from {{ ref('stg_doctors') }}
),

clinics as (
    select clinic_id, clinic_name, city from {{ ref('stg_clinics') }}
),

services as (
    select service_id, service_name, category, profitability_margin from {{ ref('stg_services') }}
),

enriched as (
    select
        a.appointment_id,
        a.patient_id,
        a.doctor_id,
        a.service_id,
        a.clinic_id,
        a.specialty,
        a.scheduled_at,
        a.actual_start,
        a.actual_end,
        a.status,
        a.appointment_date,
        a.appointment_year,
        a.appointment_month,
        a.appointment_quarter,
        a.day_of_week,
        a.appointment_hour,
        a.is_weekend,
        a.is_completed,
        a.is_cancelled,
        a.is_no_show,
        a.is_rescheduled,
        a.waiting_time_minutes,
        a.consultation_duration_minutes,
        a.channel,
        a.urgency_level,
        a.referral_source,
        a.cancellation_reason,
        a.actual_price,
        a.discount_pct,
        a.rating,
        coalesce(p.net_revenue, 0)              as net_revenue,
        coalesce(p.insurance_reimbursement, 0)  as insurance_reimbursement,
        coalesce(p.payment_method, 'Unknown')   as payment_method,
        coalesce(p.payment_status, 'Unknown')   as payment_status,
        d.doctor_name,
        d.clinic_id                             as doctor_clinic_id,
        c.clinic_name,
        c.city                                  as clinic_city,
        s.service_name,
        s.category                              as service_category,
        s.profitability_margin,

        -- Computed
        case
            when a.waiting_time_minutes <= 10 then 'Excellent'
            when a.waiting_time_minutes <= 20 then 'Good'
            when a.waiting_time_minutes <= 40 then 'Acceptable'
            else                                    'Poor'
        end                                     as wait_tier,

        case
            when a.appointment_hour between 8 and 11 then 'Morning'
            when a.appointment_hour between 12 and 14 then 'Midday'
            when a.appointment_hour between 15 and 17 then 'Afternoon'
            else                                          'Evening'
        end                                     as time_of_day

    from appointments a
    left join payments  p on a.appointment_id = p.appointment_id
    left join doctors   d on a.doctor_id      = d.doctor_id
    left join clinics   c on a.clinic_id      = c.clinic_id
    left join services  s on a.service_id     = s.service_id
)

select * from enriched
