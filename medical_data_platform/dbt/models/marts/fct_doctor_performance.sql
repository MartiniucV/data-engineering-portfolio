{{ config(materialized='table', schema='analytics') }}

select
    doctor_id,
    full_name,
    specialty,
    clinic_id,
    seniority_band,
    years_experience,
    performance_score,
    profile_rating,
    consultation_price,
    monthly_salary,
    total_appointments,
    completed_appointments,
    cancelled_appointments,
    no_show_appointments,
    avg_patient_rating,
    avg_wait_minutes,
    avg_consult_minutes,
    total_revenue,
    avg_revenue_per_appt,
    revenue_2023,
    revenue_2024,
    unique_patients,
    active_days,
    completion_rate,
    no_show_rate,
    performance_tier,

    -- Revenue per working day
    round(
        total_revenue::numeric / nullif(active_days, 0),
        2
    )                               as revenue_per_active_day,

    -- ROI: revenue vs salary cost
    round(
        total_revenue::numeric / nullif(monthly_salary * 24, 0),
        4
    )                               as revenue_to_salary_ratio,

    -- Rank within specialty
    rank() over (partition by specialty order by total_revenue desc)    as revenue_rank_in_specialty,
    rank() over (partition by specialty order by completion_rate desc)  as efficiency_rank_in_specialty,

    now()                           as dbt_updated_at
from {{ ref('int_doctor_metrics') }}
