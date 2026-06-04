-- MedInsight: Month-over-Month and Year-over-Year Revenue Analysis

WITH monthly AS (
    SELECT
        DATE_TRUNC('month', invoice_date)::DATE AS month,
        SUM(net_revenue)                        AS revenue,
        COUNT(*)                                AS invoices,
        SUM(insurance_reimbursement)            AS reimbursements
    FROM raw.billing
    GROUP BY 1
),

with_comparisons AS (
    SELECT
        month,
        revenue,
        invoices,
        reimbursements,
        LAG(revenue, 1)  OVER (ORDER BY month) AS prev_month_revenue,
        LAG(revenue, 12) OVER (ORDER BY month) AS same_month_prev_year,
        SUM(revenue)     OVER (ORDER BY month ROWS BETWEEN 11 PRECEDING AND CURRENT ROW)
                                                AS rolling_12m_revenue,
        AVG(revenue)     OVER (ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
                                                AS ma3_revenue
    FROM monthly
)

SELECT
    TO_CHAR(month, 'YYYY-MM')                               AS period,
    revenue,
    invoices,
    reimbursements,
    ROUND(revenue - prev_month_revenue, 0)                  AS mom_absolute,
    ROUND((revenue / NULLIF(prev_month_revenue, 0) - 1) * 100, 1) AS mom_pct,
    ROUND((revenue / NULLIF(same_month_prev_year, 0) - 1) * 100, 1) AS yoy_pct,
    ROUND(rolling_12m_revenue, 0)                           AS rolling_12m,
    ROUND(ma3_revenue, 0)                                   AS ma3
FROM with_comparisons
ORDER BY month;
