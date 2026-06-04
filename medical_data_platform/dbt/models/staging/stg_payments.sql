{{ config(materialized='view') }}

with source as (
    select * from {{ source('raw', 'billing') }}
)

select
    billing_id,
    appointment_id,
    patient_id,
    invoice_date::date                                              as invoice_date,
    date_part('year',  invoice_date)::integer                      as invoice_year,
    date_part('month', invoice_date)::integer                      as invoice_month,
    date_part('quarter', invoice_date)::integer                    as invoice_quarter,
    greatest(service_price::numeric(10,2), 0)                      as service_price,
    coalesce(discount_amount::numeric(10,2), 0)                    as discount_amount,
    coalesce(insurance_reimbursement::numeric(10,2), 0)            as insurance_reimbursement,
    coalesce(patient_paid::numeric(10,2), 0)                       as patient_paid,
    coalesce(tax_amount::numeric(10,2), 0)                         as tax_amount,
    coalesce(total_amount::numeric(10,2), 0)                       as total_amount,
    coalesce(refund_amount::numeric(10,2), 0)                      as refund_amount,
    greatest(coalesce(total_amount::numeric(10,2),0)
             - coalesce(refund_amount::numeric(10,2),0), 0)        as net_revenue,
    payment_method,
    payment_status,
    insurance_type,
    now()                                                          as _dbt_loaded_at
from source
where billing_id is not null
