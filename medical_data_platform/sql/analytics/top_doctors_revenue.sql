-- MedInsight: Top Doctors by Revenue with Rankings
-- Portfolio showcase query demonstrating window functions

WITH doctor_stats AS (
    SELECT
        d.doctor_id,
        d.full_name,
        d.specialty,
        c.city,
        COUNT(a.appointment_id)                                     AS total_appointments,
        COUNT(a.appointment_id) FILTER (WHERE a.status='completed') AS completed,
        SUM(b.net_revenue)                                          AS total_revenue,
        ROUND(AVG(b.net_revenue), 2)                                AS avg_revenue,
        ROUND(AVG(a.rating) FILTER (WHERE a.rating IS NOT NULL), 2) AS avg_rating,
        ROUND(
            COUNT(a.appointment_id) FILTER (WHERE a.status='completed')::NUMERIC
            / NULLIF(COUNT(a.appointment_id), 0) * 100, 1
        )                                                           AS completion_pct
    FROM raw.doctors d
    LEFT JOIN raw.appointments a ON d.doctor_id = a.doctor_id
    LEFT JOIN raw.billing      b ON a.appointment_id = b.appointment_id
    LEFT JOIN raw.clinics      c ON d.clinic_id = c.clinic_id
    GROUP BY d.doctor_id, d.full_name, d.specialty, c.city
),

ranked AS (
    SELECT
        *,
        RANK()     OVER (ORDER BY total_revenue DESC)           AS overall_rank,
        RANK()     OVER (PARTITION BY specialty ORDER BY total_revenue DESC) AS specialty_rank,
        PERCENT_RANK() OVER (ORDER BY total_revenue DESC)       AS revenue_percentile,
        NTILE(4)   OVER (ORDER BY total_revenue DESC)           AS revenue_quartile,
        LAG(total_revenue) OVER (ORDER BY total_revenue DESC)   AS prev_doctor_revenue
    FROM doctor_stats
)

SELECT
    overall_rank,
    specialty_rank,
    full_name,
    specialty,
    city,
    total_appointments,
    completed,
    total_revenue,
    avg_revenue,
    avg_rating,
    completion_pct,
    ROUND((1 - revenue_percentile) * 100, 1) AS top_pct,
    CASE revenue_quartile
        WHEN 1 THEN 'Top 25%'
        WHEN 2 THEN '25-50%'
        WHEN 3 THEN '50-75%'
        ELSE        'Bottom 25%'
    END AS performance_quartile
FROM ranked
ORDER BY overall_rank
LIMIT 20;
