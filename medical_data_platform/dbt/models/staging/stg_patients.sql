{{ config(materialized='view') }}

with source as (
    select * from {{ source('raw', 'patients') }}
),

cleaned as (
    select
        patient_id,
        cnp,
        first_name,
        last_name,
        full_name,
        gender,
        birth_date::date                                                    as birth_date,
        age::integer                                                        as age,
        blood_type,
        city,
        county,
        lower(email)                                                        as email,
        phone,
        insurance_status,
        chronic_conditions,
        least(greatest(risk_score::numeric(5,1), 0), 100)                  as risk_score,
        registration_date::date                                             as registration_date,
        is_active::boolean                                                  as is_active,

        -- Derived age bands
        case
            when age::integer between 0  and 17 then '0-17'
            when age::integer between 18 and 34 then '18-34'
            when age::integer between 35 and 49 then '35-49'
            when age::integer between 50 and 64 then '50-64'
            else                                     '65+'
        end                                                                 as age_band,

        -- Risk stratification
        case
            when risk_score::numeric < 25  then 'Low'
            when risk_score::numeric < 50  then 'Medium'
            when risk_score::numeric < 75  then 'High'
            else                                'Critical'
        end                                                                 as risk_category,

        coalesce(chronic_conditions is not null and chronic_conditions != '', false)
                                                                            as has_chronic_condition,
        now()                                                               as _dbt_loaded_at
    from source
    where patient_id is not null
)

select * from cleaned
