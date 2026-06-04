{{ config(materialized='table', schema='analytics') }}

select
    invoice_date                                    as revenue_date,
    invoice_year,
    invoice_month,
    invoice_quarter,
    city,
    specialty,
    count(billing_id)                               as num_invoices,
    sum(service_price)                              as gross_revenue,
    sum(discount_amount)                            as total_discounts,
    sum(insurance_reimbursement)                    as total_reimbursements,
    sum(patient_paid)                               as patient_revenue,
    sum(tax_amount)                                 as total_tax,
    sum(total_amount)                               as total_revenue,
    sum(refund_amount)                              as total_refunds,
    sum(net_revenue)                                as net_revenue,
    round(avg(net_revenue), 2)                      as avg_invoice_value,
    count(billing_id) filter (where payment_status = 'paid')    as paid_invoices,
    count(billing_id) filter (where payment_status = 'pending') as pending_invoices,
    now()                                           as dbt_updated_at
from {{ ref('int_revenue_metrics') }}
group by 1, 2, 3, 4, 5, 6
