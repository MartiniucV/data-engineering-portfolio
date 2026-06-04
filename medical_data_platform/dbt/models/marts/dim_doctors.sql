{{ config(materialized='table', schema='analytics') }}

-- SCD Type 1 doctor dimension (Type 2 snapshot handled separately)
select
    doctor_id,
    full_name,
    specialty,
    clinic_id,
    seniority_band,
    years_experience,
    hire_date,
    consultation_price,
    profile_rating,
    monthly_salary,
    performance_score,
    is_active,
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
    now()                   as dbt_updated_at
from {{ ref('int_doctor_metrics') }}
