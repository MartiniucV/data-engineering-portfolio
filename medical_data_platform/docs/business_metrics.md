# MedInsight Analytics Platform — Business Metrics

## Executive KPIs

| KPI | SQL Expression | Threshold | Owner |
|-----|---------------|-----------|-------|
| **Total Net Revenue** | `SUM(net_revenue)` | — | CFO |
| **YoY Revenue Growth** | `(curr / prev - 1) * 100` | Target ≥ 15% | CFO |
| **Completion Rate** | `completed / total * 100` | Target ≥ 70% | COO |
| **No-Show Rate** | `no_shows / total * 100` | Alert > 10% | Operations |
| **Cancellation Rate** | `cancelled / total * 100` | Alert > 15% | Operations |
| **Avg Wait Time** | `AVG(waiting_time_minutes)` | Target < 20 min | Operations |
| **Active Patients (90d)** | patients with visit in last 90 days | — | Growth |
| **Patient Churn Rate** | patients with no visit > 180 days / total | Alert > 25% | Growth |

## Financial Metrics

| Metric | Definition |
|--------|-----------|
| **Gross Revenue** | Sum of all `actual_price` on completed appointments |
| **Net Revenue** | Gross minus refunds |
| **Insurance Reimbursement** | Sum of `insurance_reimbursement` from billing |
| **Patient-Paid Revenue** | `patient_paid` — amount billed directly to patient |
| **Avg Invoice Value** | `AVG(net_revenue)` on completed appointments |
| **Service Profitability** | `base_price × profitability_margin` per service |
| **Revenue per Active Day** | `total_revenue / active_days` per doctor |
| **Revenue-to-Salary Ratio** | `total_revenue / (monthly_salary × 24)` per doctor |

## Operational Metrics

| Metric | Definition |
|--------|-----------|
| **Occupancy Rate** | Completed / Capacity per clinic per day |
| **Doctor Utilisation** | Completed appointments / Total scheduled slots |
| **Average Consultation Duration** | `AVG(consultation_duration_minutes)` — completed only |
| **Wait Time Tier** | Excellent (≤10 min) / Good (≤20) / Acceptable (≤40) / Poor (>40) |
| **Disruption Rate** | (Cancelled + No-shows) / Total |
| **Referral Conversion** | Appointments from doctor referral / Total |

## Patient Metrics

| Metric | Definition |
|--------|-----------|
| **Patient Lifetime Value (LTV)** | `SUM(net_revenue)` per patient, all time |
| **Avg Visits per Patient** | `COUNT(appointments) / COUNT(DISTINCT patients)` |
| **Cohort Retention Rate** | `patients_in_period_N / cohort_size` |
| **RFM Score** | Recency + Frequency + Monetary quintile scores (1–15) |
| **Churn Risk** | Low (< 180 days inactive) / Medium (180–365) / High (> 365) |
| **Engagement Level** | Inactive / Low (1–2 visits) / Medium (3–7) / High (8+) |
| **Chronic Condition Rate** | Patients with ≥ 1 chronic condition / Total |
| **Risk Category** | Low / Medium / High / Critical based on `risk_score` 0–100 |

## Doctor Performance Metrics

| Metric | Definition |
|--------|-----------|
| **Performance Tier** | Top Performer / Strong / Solid / Needs Improvement |
| **Avg Patient Rating** | `AVG(rating)` — completed, rated appointments only |
| **No-Show Rate (doctor)** | No-shows attributed to doctor's schedule |
| **Revenue Rank in Specialty** | `RANK() OVER (PARTITION BY specialty ORDER BY total_revenue DESC)` |
| **Burnout Risk Score** | Synthetic indicator 0–100 based on workload and tenure |

## Clinic Metrics

| Metric | Definition |
|--------|-----------|
| **Clinic Capacity** | `capacity` field — max daily appointments |
| **Operational Cost** | Monthly operating cost (`operational_cost`) |
| **Revenue per Capacity Unit** | `total_revenue / capacity` |
| **Region Performance** | Aggregated revenue and completion rate by geographic region |

## Segmentation Framework (RFM)

Patients are segmented into 4 groups based on RFM total score (3–15):

| Segment | Score Range | Action |
|---------|------------|--------|
| **Champions** | 11–15 | Reward loyalty, request testimonials |
| **Loyal** | 8–10 | Upsell premium services |
| **Needs Attention** | 5–7 | Re-engagement SMS/email campaign |
| **At Risk** | 3–4 | Win-back offer, dedicated outreach |
