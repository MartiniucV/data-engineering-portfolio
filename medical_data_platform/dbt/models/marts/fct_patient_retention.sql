{{ config(materialized='table', schema='analytics') }}

with visits as (
    select
        patient_id,
        appointment_date,
        date_trunc('month', appointment_date)::date as visit_month
    from {{ ref('stg_appointments') }}
    where is_completed
    group by patient_id, appointment_date, date_trunc('month', appointment_date)::date
),

first_visit as (
    select
        patient_id,
        min(visit_month) as cohort_month
    from visits
    group by patient_id
),

cohort_data as (
    select
        v.patient_id,
        f.cohort_month,
        v.visit_month,
        (
            extract(year from age(v.visit_month, f.cohort_month)) * 12
            + extract(month from age(v.visit_month, f.cohort_month))
        )::integer as period_number
    from visits v
    join first_visit f on v.patient_id = f.patient_id
),

cohort_size as (
    select
        cohort_month,
        count(distinct patient_id) as cohort_patient_count
    from first_visit
    group by cohort_month
),

retention_counts as (
    select
        cohort_month,
        period_number,
        count(distinct patient_id) as retained_patients
    from cohort_data
    group by cohort_month, period_number
),

final as (
    select
        r.cohort_month,
        r.period_number,
        r.retained_patients,
        s.cohort_patient_count,
        round(r.retained_patients::numeric / nullif(s.cohort_patient_count, 0), 4) as retention_rate,
        now() as dbt_updated_at
    from retention_counts r
    join cohort_size s on r.cohort_month = s.cohort_month
)

select * from final
