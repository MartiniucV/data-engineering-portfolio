{{ config(materialized='view') }}

with payments as (
    select * from {{ ref('stg_payments') }}
),

appointments as (
    select
        appointment_id,
        clinic_id,
        specialty,
        appointment_date,
        appointment_year,
        appointment_month,
        appointment_quarter,
        is_completed
    from {{ ref('stg_appointments') }}
),

clinics as (
    select clinic_id, clinic_name, city from {{ ref('stg_clinics') }}
),

joined as (
    select
        p.billing_id,
        p.appointment_id,
        p.patient_id,
        p.invoice_date,
        p.invoice_year,
        p.invoice_month,
        p.invoice_quarter,
        p.service_price,
        p.discount_amount,
        p.insurance_reimbursement,
        p.patient_paid,
        p.tax_amount,
        p.total_amount,
        p.refund_amount,
        p.net_revenue,
        p.payment_method,
        p.payment_status,
        p.insurance_type,
        a.clinic_id,
        a.specialty,
        c.clinic_name,
        c.city
    from payments p
    left join appointments a on p.appointment_id = a.appointment_id
    left join clinics      c on a.clinic_id       = c.clinic_id
)

select * from joined
