"""
MedInsight - Page 1: Executive Overview
"""

import sys
from pathlib import Path
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from dashboard.components.db import query
from dashboard.components.charts import (
    line_chart, bar_chart, pie_chart, apply_dark_layout, area_chart
)
from dashboard.components.filters import render_sidebar_filters, build_where_clause

st.set_page_config(page_title="Executive Overview | MedInsight", layout="wide", page_icon="📊")

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{open(css_path).read()}</style>", unsafe_allow_html=True)

st.markdown("# 📊 Executive Overview")
filters = render_sidebar_filters()
where, params = build_where_clause(filters)

# ── KPI Row ───────────────────────────────────────────────────────────────────

kpi_sql = f"""
SELECT
    COUNT(DISTINCT appointment_id)                                      AS total_appointments,
    COUNT(DISTINCT patient_id)                                          AS active_patients,
    SUM(net_revenue)                                                    AS total_revenue,
    COUNT(DISTINCT doctor_id)                                           AS active_doctors,
    ROUND(AVG(net_revenue) FILTER (WHERE is_completed), 2)             AS avg_revenue_per_appt,
    ROUND(
        COUNT(*) FILTER (WHERE is_completed)::numeric / NULLIF(COUNT(*),0) * 100, 1
    )                                                                   AS completion_pct
FROM analytics.fct_appointments
{where}
"""
kpi = query(kpi_sql, **params)

prev_sql = f"""
SELECT
    SUM(net_revenue) AS prev_revenue,
    COUNT(DISTINCT appointment_id) AS prev_appts
FROM analytics.fct_appointments
WHERE appointment_date >= ('{filters['start_date']}'::date - INTERVAL '1 year')
  AND appointment_date <  ('{filters['start_date']}'::date)
"""
prev = query(prev_sql)

if not kpi.empty and kpi.iloc[0]["total_revenue"] is not None:
    row = kpi.iloc[0]
    total_rev = float(row["total_revenue"] or 0)
    prev_rev = float(prev.iloc[0]["prev_revenue"] or 1) if not prev.empty else 1
    rev_delta = f"+{(total_rev/prev_rev - 1)*100:.1f}% YoY" if prev_rev else None

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Revenue", f"RON {total_rev:,.0f}", delta=rev_delta)
    c2.metric("Appointments", f"{int(row['total_appointments'] or 0):,}")
    c3.metric("Active Patients", f"{int(row['active_patients'] or 0):,}")
    c4.metric("Active Doctors", f"{int(row['active_doctors'] or 0):,}")
    c5.metric("Avg Revenue/Appt", f"RON {float(row['avg_revenue_per_appt'] or 0):,.0f}")
    c6.metric("Completion Rate", f"{float(row['completion_pct'] or 0):.1f}%")

st.markdown("---")

# ── Revenue Trend ─────────────────────────────────────────────────────────────

col1, col2 = st.columns([2, 1])

with col1:
    rev_trend_sql = f"""
    SELECT
        TO_CHAR(appointment_date, 'YYYY-MM') AS month,
        SUM(net_revenue)                     AS revenue,
        COUNT(appointment_id)                AS appointments
    FROM analytics.fct_appointments
    {where}
    GROUP BY 1 ORDER BY 1
    """
    rev_trend = query(rev_trend_sql, **params)
    if not rev_trend.empty:
        fig = line_chart(rev_trend, "month", "revenue", "Monthly Revenue (RON)", height=350)
        st.plotly_chart(fig, use_container_width=True)

with col2:
    status_sql = f"""
    SELECT status, COUNT(*) AS count
    FROM analytics.fct_appointments
    {where}
    GROUP BY 1
    """
    status_df = query(status_sql, **params)
    if not status_df.empty:
        fig = pie_chart(status_df, "count", "status", "Appointment Status", height=350)
        st.plotly_chart(fig, use_container_width=True)

# ── Clinic Comparison ─────────────────────────────────────────────────────────

st.markdown("### Clinic Performance Comparison")
clinic_sql = f"""
SELECT
    clinic_city,
    COUNT(appointment_id)                               AS appointments,
    SUM(net_revenue)                                    AS revenue,
    ROUND(AVG(rating) FILTER (WHERE rating IS NOT NULL), 2) AS avg_rating,
    ROUND(COUNT(*) FILTER (WHERE is_completed)::numeric / NULLIF(COUNT(*),0)*100, 1) AS completion_pct
FROM analytics.fct_appointments
{where}
GROUP BY 1 ORDER BY revenue DESC
"""
clinic_df = query(clinic_sql, **params)

if not clinic_df.empty:
    col1, col2 = st.columns(2)
    with col1:
        fig = bar_chart(clinic_df, "clinic_city", "revenue", "Revenue by Clinic (RON)", height=350)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = bar_chart(clinic_df, "clinic_city", "appointments", "Appointments by Clinic", height=350)
        st.plotly_chart(fig, use_container_width=True)

# ── Specialty Mix ─────────────────────────────────────────────────────────────

st.markdown("### Revenue by Specialty")
spec_sql = f"""
SELECT
    specialty,
    SUM(net_revenue) AS revenue,
    COUNT(*)         AS appointments
FROM analytics.fct_appointments
{where}
GROUP BY 1 ORDER BY revenue DESC
"""
spec_df = query(spec_sql, **params)
if not spec_df.empty:
    col1, col2 = st.columns(2)
    with col1:
        fig = bar_chart(spec_df, "specialty", "revenue", "Revenue by Specialty", orientation="h", height=400)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = pie_chart(spec_df, "revenue", "specialty", "Revenue Mix by Specialty", height=400)
        st.plotly_chart(fig, use_container_width=True)

# ── Export ────────────────────────────────────────────────────────────────────

if not clinic_df.empty:
    st.download_button("Export Clinic Summary CSV", clinic_df.to_csv(index=False),
                       "clinic_summary.csv", "text/csv")
