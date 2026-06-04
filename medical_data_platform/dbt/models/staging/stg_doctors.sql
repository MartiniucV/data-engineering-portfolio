{{ config(materialized='view') }}

with source as (
    select * from {{ source('raw', 'doctors') }}
),

cleaned as (
    select
        doctor_id,
        first_name,
        last_name,
        full_name,
        gender,
        specialty,
        clinic_id,
        years_experience::integer                                           as years_experience,
        hire_date::date                                                     as hire_date,
        consultation_price::numeric(10,2)                                   as consultation_price,
        least(greatest(rating::numeric(3,1), 1.0), 5.0)                    as rating,
        monthly_salary::numeric(12,2)                                       as monthly_salary,
        least(greatest(performance_score::numeric(5,1), 0), 100)            as performance_score,
        is_active::boolean                                                  as is_active,
        lower(email)                                                        as email,
        phone,

        -- Derived
        case
            when years_experience between 0 and 4   then 'Junior'
            when years_experience between 5 and 9   then 'Mid'
            when years_experience between 10 and 19 then 'Senior'
            else                                         'Principal'
        end                                                                 as seniority_band,

        date_part('year', age(current_date, hire_date))::integer            as tenure_years,
        now()                                                               as _dbt_loaded_at
    from source
    where doctor_id is not null
      and full_name is not null
)

select * from cleaned
