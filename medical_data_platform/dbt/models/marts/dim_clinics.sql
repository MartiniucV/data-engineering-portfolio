{{ config(materialized='table', schema='analytics') }}

with clinics as (
    select * from {{ ref('stg_clinics') }}
),

clinic_stats as (
    select
        clinic_id,
        count(appointment_id)                                   as total_appointments,
        count(appointment_id) filter (where is_completed)       as completed_appointments,
        sum(net_revenue)                                        as total_revenue,
        count(distinct patient_id)                              as unique_patients,
        count(distinct doctor_id)                               as active_doctors,
        round(avg(waiting_time_minutes)::numeric, 1)            as avg_wait_minutes
    from {{ ref('int_appointment_metrics') }}
    group by clinic_id
)

select
    c.clinic_id,
    c.clinic_name,
    c.city,
    c.county,
    c.address,
    c.phone,
    c.capacity,
    c.opening_date,
    c.is_active,
    coalesce(s.total_appointments, 0)       as total_appointments,
    coalesce(s.completed_appointments, 0)   as completed_appointments,
    coalesce(s.total_revenue, 0)            as total_revenue,
    coalesce(s.unique_patients, 0)          as unique_patients,
    coalesce(s.active_doctors, 0)           as active_doctors,
    s.avg_wait_minutes,
    now()                                   as dbt_updated_at
from clinics c
left join clinic_stats s on c.clinic_id = s.clinic_id
