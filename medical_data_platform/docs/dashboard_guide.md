# MedInsight Analytics Platform — Dashboard Guide

## Overview

The MedInsight dashboard is a Streamlit multi-page application with a premium dark
medical theme. It connects to the PostgreSQL `analytics` schema (dbt gold layer) and
uses 5-minute query caching for performance.

**Launch:** `streamlit run dashboard/dashboard.py`
**Default URL:** http://localhost:8501

---

## Page 1 — Executive Overview

**Audience:** C-suite, clinic directors
**Purpose:** Single-pane view of network health

**Widgets:**
- 6 KPI glass cards: Total Revenue, Appointments, Active Patients, Active Doctors, Avg Revenue/Appt, Completion Rate
- YoY revenue delta on revenue card
- Insight banner triggered when completion rate < 68%
- Monthly net revenue area chart (2-year trend)
- Appointment status mix pie chart
- Clinic performance leaderboard (bar charts: revenue + volume)
- Revenue by specialty (bar + pie)
- CSV export of clinic summary

**Filters apply to:** all charts on this page

---

## Page 2 — Doctor Performance

**Audience:** Medical directors, HR
**Purpose:** Identify top performers, utilisation gaps, and rating drivers

**Widgets:**
- 4 KPI cards: Doctors Active, Avg Revenue/Doctor, Network Avg Rating, Avg Completion
- Top-3 doctor utilisation gauges (completion rate)
- Full ranking table (scrollable, configurable top-N)
- Revenue vs. Patient Rating scatter (bubble = appointment volume, colour = specialty)
- Top-15 doctors by appointment volume (horizontal bar)
- Specialty breakdown: revenue + completion rate
- Appointment load heatmap: Day of Week × Hour of Day

---

## Page 3 — Patient Analytics

**Audience:** Marketing, patient experience teams
**Purpose:** Demographics, retention, LTV, churn risk

**Widgets:**
- 5 KPI cards: Total Patients, Active, High Churn Risk, Avg LTV, Chronic Conditions
- Churn alert insight banner (> 25% threshold)
- Demographics 2×3 grid: Gender, Age Band, Insurance, Risk Category, Engagement, Churn Risk
- Geography: Patients by City, Total LTV by City
- Cohort Retention heatmap (months 0–12, all cohorts since 2020)
- LTV by Engagement Level (bar) + Visits vs LTV scatter by Churn Risk
- Top chronic conditions horizontal bar (up to 15 conditions)

---

## Page 4 — Financial Analytics

**Audience:** CFO, finance team
**Purpose:** Revenue deep-dive, profitability, payment behaviour

**Widgets:**
- 6 KPI cards: Net Revenue, Gross Revenue, Reimbursements, Discounts, Avg Invoice, Revenue Days
- Monthly revenue breakdown area chart (net + gross)
- Insurance reimbursements trend line chart
- Revenue by Specialty (horizontal bar) + Revenue by City (bar)
- Service profitability table: Revenue by Service + Margin % (horizontal bars)
- Payment method mix: transaction volume pie + revenue share pie

---

## Page 5 — Operational Metrics

**Audience:** Operations managers, clinic coordinators
**Purpose:** Monitor disruption rates, wait times, booking behaviour

**Widgets:**
- 6 KPI cards: Cancellation Rate, No-Show Rate, Avg Wait, Max Wait, Avg Consult Duration, Operating Days
- Disruption rate alert (> 25% combined threshold)
- 3 health gauges: Completion Rate, Wait Time Score, Show-Up Rate
- Monthly volume by status (area: completed/cancelled/no-shows)
- Disruption rates trend line (%): cancellations + no-shows
- Cancellation reasons horizontal bar
- No-show rate by booking channel bar chart
- Wait Time heatmap: Day of Week × Hour
- Urgency level pie + Booking channel pie

---

## Page 6 — Predictive Analytics

**Audience:** Strategy, data science team
**Purpose:** Forward-looking insights: forecast, churn AI, anomaly detection

**Widgets:**
- Revenue Forecast chart: historical (red line + fill) + 6-month projection (teal dotted) + confidence band
- No-show risk by channel (horizontal bar) + by day of week (bar)
- Churn Risk KPI row: High / Medium / Low patient counts
- Churn alert insight banner
- Inactivity vs. LTV by Churn Risk scatter
- Churn segmentation detail table
- Doctor Utilisation scatter: Completion Rate vs. Revenue (bubble = unique patients)
- Billing Anomaly Indicators: anomalous months by Z-score

---

## Sidebar Filters

All filters apply globally to the page-level SQL queries:

| Filter | Type | Default |
|--------|------|---------|
| Date Range (From) | Date picker | 2020-01-01 |
| Date Range (To) | Date picker | 2024-12-31 |
| Specialty | Dropdown | All |
| City | Dropdown | All |
| Doctor | Dropdown | All |

---

## Performance Notes

- All SQL queries are cached with `@st.cache_data(ttl=300)` (5 minutes)
- Heavy aggregations run server-side in PostgreSQL — Streamlit never loads raw tables
- The SQLAlchemy engine pool is cached with `@st.cache_resource`
- To force a refresh, click "Clear Cache" in the Streamlit top-right menu

---

## Customisation

### Change the colour theme

Edit `dashboard/assets/style.css` CSS custom properties:
```css
--red: #d63031;        /* medical red accent */
--teal: #00d4aa;       /* secondary accent */
--bg-primary: #060c16; /* main background */
```

### Add a new chart to a page

1. Write the SQL query using `query(sql, **params)`
2. Call the appropriate chart function from `dashboard/components/charts.py`
3. Wrap in `st.plotly_chart(fig, use_container_width=True)`

### Add a new filter

Edit `dashboard/components/filters.py` — add to `render_sidebar_filters()` and
`build_where_clause()`.
