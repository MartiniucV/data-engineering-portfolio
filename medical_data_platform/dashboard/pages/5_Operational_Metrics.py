"""
MedInsight - Page 5: Operational Metrics
"""

import sys
from pathlib import Path
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from dashboard.components.db import query
from dashboard.components.charts import bar_chart, line_chart, heatmap, pie_chart, area_chart
from dashboard.components.filters import render_sidebar_filters, build_where_clause

st.set_page_config(page_title="Operational Metrics | MedInsight", layout="wide", page_icon="⚙️")
css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{open(css_path).read()}</style>", unsafe_allow_html=True)

st.markdown("# ⚙️ Operational Metrics")
filters = render_sidebar_filters()
where, params = build_where_clause(filters)

# ── Operational KPIs ──────────────────────────────────────────────────────────

ops_kpi_sql = f"""
SELECT
    ROUND(COUNT(*) FILTER (WHERE is_cancelled)::numeric / NULLIF(COUNT(*),0)*100, 2) AS cancellation_rate,
    ROUND(COUNT(*) FILTER (WHERE is_no_show)::numeric   / NULLIF(COUNT(*),0)*100, 2) AS no_show_rate,
    ROUND(AVG(waiting_time_minutes)::numeric, 1)  AS avg_wait_min,
    MAX(waiting_time_minutes)                     AS max_wait_min,
    ROUND(AVG(consultation_duration_minutes) FILTER (WHERE is_completed)::numeric, 1) AS avg_consult_min,
    COUNT(DISTINCT appointment_date)              AS operating_days
FROM analytics.fct_appointments
{where}
"""
ops_kpi = query(ops_kpi_sql, **params)

if not ops_kpi.empty:
    row = ops_kpi.iloc[0]
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Cancellation Rate", f"{float(row.get('cancellation_rate') or 0):.1f}%")
    c2.metric("No-Show Rate", f"{float(row.get('no_show_rate') or 0):.1f}%")
    c3.metric("Avg Wait Time", f"{float(row.get('avg_wait_min') or 0):.0f} min")
    c4.metric("Max Wait Time", f"{int(row.get('max_wait_min') or 0)} min")
    c5.metric("Avg Consult Duration", f"{float(row.get('avg_consult_min') or 0):.0f} min")
    c6.metric("Operating Days", f"{int(row.get('operating_days') or 0):,}")

st.markdown("---")

# ── Daily Volume Trend ────────────────────────────────────────────────────────

vol_sql = f"""
SELECT
    TO_CHAR(appointment_date, 'YYYY-MM') AS month,
    COUNT(*)                             AS total,
    COUNT(*) FILTER (WHERE is_completed) AS completed,
    COUNT(*) FILTER (WHERE is_cancelled) AS cancelled,
    COUNT(*) FILTER (WHERE is_no_show)   AS no_shows
FROM analytics.fct_appointments
{where}
GROUP BY 1 ORDER BY 1
"""
vol_df = query(vol_sql, **params)

if not vol_df.empty:
    col1, col2 = st.columns(2)
    with col1:
        fig = area_chart(vol_df, "month", ["completed", "cancelled", "no_shows"],
                         "Monthly Appointment Volume by Status", height=380)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        rate_sql = f"""
        SELECT
            TO_CHAR(appointment_date, 'YYYY-MM') AS month,
            ROUND(COUNT(*) FILTER (WHERE is_cancelled)::numeric / NULLIF(COUNT(*),0)*100, 1) AS cancellation_pct,
            ROUND(COUNT(*) FILTER (WHERE is_no_show)::numeric   / NULLIF(COUNT(*),0)*100, 1) AS no_show_pct
        FROM analytics.fct_appointments
        {where}
        GROUP BY 1 ORDER BY 1
        """
        rate_df = query(rate_sql, **params)
        if not rate_df.empty:
            fig = line_chart(rate_df, "month", ["cancellation_pct", "no_show_pct"],
                             "Cancellation & No-Show Rate (%)", height=380)
            st.plotly_chart(fig, use_container_width=True)

# ── Cancellation Reasons ──────────────────────────────────────────────────────

st.markdown("### Cancellation & No-Show Analysis")

canc_sql = f"""
SELECT
    cancellation_reason,
    COUNT(*) AS count
FROM analytics.fct_appointments
{where} AND cancellation_reason IS NOT NULL
GROUP BY 1 ORDER BY count DESC
"""
canc_df = query(canc_sql, **params)

col1, col2 = st.columns(2)
with col1:
    if not canc_df.empty:
        fig = bar_chart(canc_df, "cancellation_reason", "count",
                        "Cancellation Reasons", orientation="h", height=350)
        st.plotly_chart(fig, use_container_width=True)

with col2:
    channel_sql = f"""
    SELECT
        channel,
        ROUND(COUNT(*) FILTER (WHERE is_no_show)::numeric / NULLIF(COUNT(*),0)*100, 1) AS no_show_rate,
        COUNT(*) AS total
    FROM analytics.fct_appointments
    {where}
    GROUP BY 1 ORDER BY no_show_rate DESC
    """
    ch_df = query(channel_sql, **params)
    if not ch_df.empty:
        fig = bar_chart(ch_df, "channel", "no_show_rate",
                        "No-Show Rate by Booking Channel (%)", height=350)
        st.plotly_chart(fig, use_container_width=True)

# ── Wait Time Heatmap ─────────────────────────────────────────────────────────

st.markdown("### Wait Time Analysis")
wait_sql = f"""
SELECT
    TRIM(day_of_week)   AS dow,
    appointment_hour    AS hour,
    ROUND(AVG(waiting_time_minutes)::numeric, 1) AS avg_wait
FROM analytics.fct_appointments
{where} AND waiting_time_minutes IS NOT NULL
GROUP BY 1, 2
"""
wait_df = query(wait_sql, **params)

if not wait_df.empty:
    dow_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    wait_df["dow"] = pd.Categorical(wait_df["dow"].str.strip(), categories=dow_order, ordered=True)
    pivot = wait_df.pivot_table(index="dow", columns="hour", values="avg_wait", fill_value=0)
    pivot = pivot.reindex([d for d in dow_order if d in pivot.index])
    fig = heatmap(pivot, "Average Wait Time (min): Day × Hour", height=350)
    st.plotly_chart(fig, use_container_width=True)

# ── Urgency & Channel Mix ─────────────────────────────────────────────────────

st.markdown("### Urgency Level & Channel Mix")
urgency_sql = f"""
SELECT urgency_level, COUNT(*) AS cnt FROM analytics.fct_appointments
{where} GROUP BY 1
"""
urgency_df = query(urgency_sql, **params)

channel_mix_sql = f"""
SELECT channel, COUNT(*) AS cnt FROM analytics.fct_appointments
{where} GROUP BY 1
"""
channel_mix_df = query(channel_mix_sql, **params)

col1, col2 = st.columns(2)
with col1:
    if not urgency_df.empty:
        fig = pie_chart(urgency_df, "cnt", "urgency_level", "Urgency Level Mix", height=300)
        st.plotly_chart(fig, use_container_width=True)
with col2:
    if not channel_mix_df.empty:
        fig = pie_chart(channel_mix_df, "cnt", "channel", "Booking Channel Mix", height=300)
        st.plotly_chart(fig, use_container_width=True)
