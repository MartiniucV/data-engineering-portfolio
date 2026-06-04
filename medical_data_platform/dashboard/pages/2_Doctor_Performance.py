"""
MedInsight - Page 2: Doctor Performance
"""

import sys
from pathlib import Path
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from dashboard.components.db import query
from dashboard.components.charts import bar_chart, scatter_chart, heatmap, apply_dark_layout
from dashboard.components.filters import render_sidebar_filters, build_where_clause
import plotly.graph_objects as go

st.set_page_config(page_title="Doctor Performance | MedInsight", layout="wide", page_icon="👨‍⚕️")
css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{open(css_path).read()}</style>", unsafe_allow_html=True)

st.markdown("# 👨‍⚕️ Doctor Performance")
filters = render_sidebar_filters()
where, params = build_where_clause(filters)

# ── Top Doctors KPIs ──────────────────────────────────────────────────────────

top_sql = f"""
SELECT
    doctor_name,
    specialty,
    COUNT(appointment_id)                               AS appointments,
    SUM(net_revenue)                                    AS revenue,
    ROUND(AVG(rating) FILTER (WHERE rating IS NOT NULL), 2) AS avg_rating,
    ROUND(COUNT(*) FILTER (WHERE is_completed)::numeric / NULLIF(COUNT(*),0)*100, 1) AS completion_pct,
    ROUND(AVG(waiting_time_minutes)::numeric, 1)        AS avg_wait_min,
    COUNT(DISTINCT patient_id)                          AS unique_patients
FROM analytics.fct_appointments
{where}
GROUP BY doctor_name, specialty
ORDER BY revenue DESC
"""
doc_df = query(top_sql, **params)

if doc_df.empty:
    st.warning("No data for selected filters.")
    st.stop()

# Summary KPIs
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Doctors", len(doc_df))
c2.metric("Avg Revenue/Doctor", f"RON {doc_df['revenue'].mean():,.0f}")
c3.metric("Avg Rating", f"{doc_df['avg_rating'].mean():.2f} ⭐")
c4.metric("Avg Completion Rate", f"{doc_df['completion_pct'].mean():.1f}%")

st.markdown("---")

# ── Ranking Table ─────────────────────────────────────────────────────────────

st.markdown("### Top Doctors Ranking")
top_n = st.slider("Show top N doctors", min_value=5, max_value=50, value=20)
top_docs = doc_df.head(top_n).reset_index(drop=True)
top_docs.index += 1
top_docs["revenue"] = top_docs["revenue"].apply(lambda x: f"RON {x:,.0f}")
st.dataframe(top_docs, use_container_width=True, height=400)

# ── Revenue vs Rating Scatter ─────────────────────────────────────────────────

col1, col2 = st.columns(2)

with col1:
    fig = scatter_chart(
        doc_df, x="avg_rating", y="revenue", color="specialty",
        size="appointments", hover_data=["doctor_name", "completion_pct"],
        title="Revenue vs. Patient Rating", height=400
    )
    st.plotly_chart(fig, use_container_width=True)

with col2:
    fig = bar_chart(doc_df.head(15), "doctor_name", "appointments",
                    "Top 15 Doctors by Appointments", orientation="h", height=400)
    st.plotly_chart(fig, use_container_width=True)

# ── Specialty Analysis ────────────────────────────────────────────────────────

st.markdown("### Performance by Specialty")
spec_agg_sql = f"""
SELECT
    specialty,
    COUNT(DISTINCT doctor_name)                         AS num_doctors,
    COUNT(appointment_id)                               AS total_appointments,
    SUM(net_revenue)                                    AS total_revenue,
    ROUND(AVG(net_revenue) FILTER (WHERE is_completed),2) AS avg_appt_revenue,
    ROUND(AVG(rating) FILTER (WHERE rating IS NOT NULL),2) AS avg_rating,
    ROUND(COUNT(*) FILTER (WHERE is_completed)::numeric / NULLIF(COUNT(*),0)*100, 1) AS completion_pct,
    ROUND(COUNT(*) FILTER (WHERE is_no_show)::numeric / NULLIF(COUNT(*),0)*100, 1)   AS no_show_pct
FROM analytics.fct_appointments
{where}
GROUP BY 1 ORDER BY total_revenue DESC
"""
spec_agg = query(spec_agg_sql, **params)

if not spec_agg.empty:
    col1, col2 = st.columns(2)
    with col1:
        fig = bar_chart(spec_agg, "specialty", "total_revenue",
                        "Revenue by Specialty", orientation="h", height=400)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = bar_chart(spec_agg, "specialty", "completion_pct",
                        "Completion Rate by Specialty (%)", orientation="h", height=400)
        st.plotly_chart(fig, use_container_width=True)

# ── Doctor Heatmap: Appointments by Day & Hour ────────────────────────────────

st.markdown("### Appointment Load Heatmap (Day of Week × Hour)")
heat_sql = f"""
SELECT
    TRIM(day_of_week)   AS dow,
    appointment_hour    AS hour,
    COUNT(*)            AS appointments
FROM analytics.fct_appointments
{where}
GROUP BY 1, 2
"""
heat_df = query(heat_sql, **params)
if not heat_df.empty:
    dow_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    heat_df["dow"] = pd.Categorical(heat_df["dow"].str.strip(), categories=dow_order, ordered=True)
    pivot = heat_df.pivot_table(index="dow", columns="hour", values="appointments", fill_value=0)
    pivot = pivot.reindex([d for d in dow_order if d in pivot.index])
    fig = heatmap(pivot, "Appointment Volume: Day × Hour", height=350)
    st.plotly_chart(fig, use_container_width=True)

# ── Export ────────────────────────────────────────────────────────────────────
st.download_button("Export Doctor Ranking CSV", doc_df.to_csv(index=False),
                   "doctor_performance.csv", "text/csv")
