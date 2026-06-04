"""
MedInsight - Page 4: Financial Analytics
"""

import sys
from pathlib import Path
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from dashboard.components.db import query
from dashboard.components.charts import (
    bar_chart, pie_chart, line_chart, area_chart, waterfall_chart, apply_dark_layout
)
from dashboard.components.filters import render_sidebar_filters, build_where_clause
import plotly.graph_objects as go

st.set_page_config(page_title="Financial Analytics | MedInsight", layout="wide", page_icon="💰")
css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{open(css_path).read()}</style>", unsafe_allow_html=True)

st.markdown("# 💰 Financial Analytics")
filters = render_sidebar_filters()
where, params = build_where_clause(filters)

# ── Revenue KPIs ──────────────────────────────────────────────────────────────

fin_kpi_sql = f"""
SELECT
    SUM(net_revenue)                                AS net_revenue,
    SUM(insurance_reimbursement)                    AS total_reimbursements,
    SUM(actual_price)                               AS gross_revenue,
    SUM(actual_price) - SUM(net_revenue)            AS total_discounts,
    ROUND(AVG(net_revenue) FILTER (WHERE is_completed), 2) AS avg_invoice,
    COUNT(DISTINCT appointment_date)                AS revenue_days
FROM analytics.fct_appointments
{where}
"""
fin = query(fin_kpi_sql, **params)

if not fin.empty:
    row = fin.iloc[0]
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Net Revenue", f"RON {float(row.get('net_revenue') or 0):,.0f}")
    c2.metric("Gross Revenue", f"RON {float(row.get('gross_revenue') or 0):,.0f}")
    c3.metric("Reimbursements", f"RON {float(row.get('total_reimbursements') or 0):,.0f}")
    c4.metric("Discounts Given", f"RON {float(row.get('total_discounts') or 0):,.0f}")
    c5.metric("Avg Invoice", f"RON {float(row.get('avg_invoice') or 0):,.0f}")
    c6.metric("Revenue Days", f"{int(row.get('revenue_days') or 0):,}")

st.markdown("---")

# ── Monthly Revenue Trend ──────────────────────────────────────────────────────

monthly_sql = f"""
SELECT
    TO_CHAR(appointment_date, 'YYYY-MM') AS month,
    SUM(net_revenue)                     AS net_revenue,
    SUM(insurance_reimbursement)         AS reimbursements,
    SUM(actual_price)                    AS gross_revenue
FROM analytics.fct_appointments
{where}
GROUP BY 1 ORDER BY 1
"""
monthly_df = query(monthly_sql, **params)

if not monthly_df.empty:
    col1, col2 = st.columns(2)
    with col1:
        fig = area_chart(monthly_df, "month", ["net_revenue", "gross_revenue"],
                         "Monthly Revenue Breakdown (RON)", height=380)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = line_chart(monthly_df, "month", "reimbursements",
                         "Monthly Insurance Reimbursements (RON)", height=380)
        st.plotly_chart(fig, use_container_width=True)

# ── Revenue by Specialty & Clinic ─────────────────────────────────────────────

st.markdown("### Revenue Breakdown")
col1, col2 = st.columns(2)

spec_rev_sql = f"""
SELECT specialty, SUM(net_revenue) AS revenue,
       ROUND(SUM(net_revenue) / SUM(SUM(net_revenue)) OVER () * 100, 1) AS pct
FROM analytics.fct_appointments
{where}
GROUP BY 1 ORDER BY revenue DESC
"""
spec_rev = query(spec_rev_sql, **params)

clinic_rev_sql = f"""
SELECT clinic_city AS city, SUM(net_revenue) AS revenue,
       COUNT(DISTINCT doctor_id) AS doctors
FROM analytics.fct_appointments
{where}
GROUP BY 1 ORDER BY revenue DESC
"""
clinic_rev = query(clinic_rev_sql, **params)

with col1:
    if not spec_rev.empty:
        fig = bar_chart(spec_rev, "specialty", "revenue",
                        "Revenue by Specialty (RON)", orientation="h", height=350)
        st.plotly_chart(fig, use_container_width=True)
with col2:
    if not clinic_rev.empty:
        fig = bar_chart(clinic_rev, "city", "revenue",
                        "Revenue by Clinic City (RON)", height=350)
        st.plotly_chart(fig, use_container_width=True)

# ── Service Profitability ─────────────────────────────────────────────────────

st.markdown("### Service Profitability Analysis")
svc_rev_sql = f"""
SELECT
    service_name,
    service_category,
    COUNT(appointment_id)           AS appointments,
    SUM(net_revenue)                AS total_revenue,
    ROUND(AVG(net_revenue), 2)      AS avg_revenue,
    ROUND(AVG(profitability_margin)*100, 1) AS avg_margin_pct
FROM analytics.fct_appointments
{where}
GROUP BY service_name, service_category
ORDER BY total_revenue DESC
LIMIT 16
"""
svc_df = query(svc_rev_sql, **params)

if not svc_df.empty:
    col1, col2 = st.columns(2)
    with col1:
        fig = bar_chart(svc_df, "service_name", "total_revenue",
                        "Top Services by Revenue", orientation="h", height=420)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = bar_chart(svc_df, "service_name", "avg_margin_pct",
                        "Avg Profitability Margin by Service (%)", orientation="h", height=420)
        st.plotly_chart(fig, use_container_width=True)

# ── Payment Methods ────────────────────────────────────────────────────────────

st.markdown("### Payment Methods")
pay_sql = f"""
SELECT
    payment_method,
    COUNT(*)            AS transactions,
    SUM(net_revenue)    AS revenue
FROM analytics.fct_appointments
{where} AND payment_method IS NOT NULL
GROUP BY 1 ORDER BY revenue DESC
"""
pay_df = query(pay_sql, **params)

if not pay_df.empty:
    col1, col2 = st.columns(2)
    with col1:
        fig = pie_chart(pay_df, "transactions", "payment_method",
                        "Transactions by Payment Method", height=350)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = pie_chart(pay_df, "revenue", "payment_method",
                        "Revenue by Payment Method", height=350)
        st.plotly_chart(fig, use_container_width=True)

if not svc_df.empty:
    st.download_button("Export Service Revenue CSV", svc_df.to_csv(index=False),
                       "service_revenue.csv", "text/csv")
