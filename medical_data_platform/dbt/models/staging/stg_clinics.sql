{{ config(materialized='view') }}

with source as (
    select * from {{ source('raw', 'clinics') }}
),

renamed as (
    select
        clinic_id,
        name                                    as clinic_name,
        city,
        county,
        address,
        phone,
        capacity::integer                       as capacity,
        opening_date::date                      as opening_date,
        is_active::boolean                      as is_active,
        now()                                   as _dbt_loaded_at
    from source
    where clinic_id is not null
)

select * from renamed
