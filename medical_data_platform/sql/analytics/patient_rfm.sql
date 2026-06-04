-- MedInsight: RFM Patient Segmentation
-- Recency (days since last visit), Frequency (visits), Monetary (total spend)

WITH patient_stats AS (
    SELECT
        p.patient_id,
        p.full_name,
        p.city,
        p.insurance_status,
        p.age,
        CURRENT_DATE - MAX(a.scheduled_at::DATE)     AS recency_days,
        COUNT(a.appointment_id)                       AS frequency,
        SUM(b.net_revenue)                            AS monetary
    FROM raw.patients p
    LEFT JOIN raw.appointments a ON p.patient_id = a.patient_id AND a.status = 'completed'
    LEFT JOIN raw.billing      b ON a.appointment_id = b.appointment_id
    GROUP BY p.patient_id, p.full_name, p.city, p.insurance_status, p.age
    HAVING COUNT(a.appointment_id) > 0
),

rfm_scored AS (
    SELECT
        *,
        NTILE(5) OVER (ORDER BY recency_days ASC)  AS r_score,
        NTILE(5) OVER (ORDER BY frequency DESC)    AS f_score,
        NTILE(5) OVER (ORDER BY monetary DESC)     AS m_score
    FROM patient_stats
),

segmented AS (
    SELECT
        *,
        r_score + f_score + m_score AS rfm_total,
        CASE
            WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions'
            WHEN r_score >= 3 AND f_score >= 3                   THEN 'Loyal'
            WHEN r_score >= 4 AND f_score <= 2                   THEN 'New'
            WHEN r_score <= 2 AND f_score >= 3                   THEN 'At Risk'
            WHEN r_score <= 2 AND f_score <= 2                   THEN 'Lost'
            ELSE                                                       'Promising'
        END AS segment
    FROM rfm_scored
)

SELECT
    segment,
    COUNT(*)                        AS patients,
    ROUND(AVG(recency_days), 0)     AS avg_recency,
    ROUND(AVG(frequency), 1)        AS avg_frequency,
    ROUND(AVG(monetary), 0)         AS avg_monetary,
    ROUND(SUM(monetary), 0)         AS total_revenue
FROM segmented
GROUP BY segment
ORDER BY total_revenue DESC;
