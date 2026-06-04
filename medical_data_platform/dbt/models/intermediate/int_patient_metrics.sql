{{ config(materialized='view') }}

with patients as (
    select * from {{ ref('stg_patients') }}
),

appointments as (
    select * from {{ ref('int_appointment_metrics') }}
),

patient_agg as (
    select
        patient_id,
        count(appointment_id)                                                   as total_visits,
        count(appointment_id) filter (where is_completed)                       as completed_visits,
        count(appointment_id) filter (where is_no_show)                         as no_show_count,
        count(appointment_id) filter (where is_cancelled)                       as cancellation_count,
        count(distinct specialty)                                               as distinct_specialties,
        count(distinct doctor_id)                                               as distinct_doctors,
        count(distinct clinic_id)                                               as distinct_clinics,
        min(appointment_date)                                                   as first_visit_date,
        max(appointment_date)                                                   as last_visit_date,
        sum(net_revenue)                                                        as lifetime_value,
        round(avg(net_revenue) filter (where is_completed), 2)                 as avg_spend_per_visit,
        round(avg(rating) filter (where rating is not null), 2)                as avg_rating_given,
        count(appointment_id) filter (where appointment_year = 2024)           as visits_2024,
        count(appointment_id) filter (where appointment_year = 2023)           as visits_2023,
        -- Recency
        current_date - max(appointment_date)                                   as days_since_last_visit
    from appointments
    group by patient_id
),

final as (
    select
        p.patient_id,
        p.full_name,
        p.gender,
        p.age,
        p.age_band,
        p.blood_type,
        p.city,
        p.county,
        p.insurance_status,
        p.chronic_conditions,
        p.has_chronic_condition,
        p.risk_score,
        p.risk_category,
        p.registration_date,
        p.is_active,
        coalesce(a.total_visits, 0)             as total_visits,
        coalesce(a.completed_visits, 0)         as completed_visits,
        coalesce(a.no_show_count, 0)            as no_show_count,
        coalesce(a.cancellation_count, 0)       as cancellation_count,
        coalesce(a.distinct_specialties, 0)     as distinct_specialties,
        coalesce(a.distinct_doctors, 0)         as distinct_doctors,
        a.first_visit_date,
        a.last_visit_date,
        coalesce(a.lifetime_value, 0)           as lifetime_value,
        a.avg_spend_per_visit,
        a.avg_rating_given,
        coalesce(a.visits_2024, 0)              as visits_2024,
        coalesce(a.visits_2023, 0)              as visits_2023,
        coalesce(a.days_since_last_visit, 9999) as days_since_last_visit,

        -- Churn risk (heuristic)
        case
            when coalesce(a.days_since_last_visit, 9999) > 365 then 'High'
            when coalesce(a.days_since_last_visit, 9999) > 180 then 'Medium'
            else                                                     'Low'
        end                                     as churn_risk,

        -- Engagement score
        case
            when coalesce(a.total_visits, 0) = 0          then 'Inactive'
            when coalesce(a.total_visits, 0) between 1 and 2 then 'Low'
            when coalesce(a.total_visits, 0) between 3 and 7 then 'Medium'
            else                                               'High'
        end                                     as engagement_level

    from patients p
    left join patient_agg a on p.patient_id = a.patient_id
)

select * from final
