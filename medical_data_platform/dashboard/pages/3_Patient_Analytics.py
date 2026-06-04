"""
MedInsight - Page 3: Patient Analytics
"""

import sys
from pathlib import Path
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from dashboard.components.db import query
from dashboard.components.charts import bar_chart, pie_chart, line_chart, scatter_chart, heatmap
from dashboard.components.filters import render_sidebar_filters, build_where_clause

st.set_page_config(page_title="Patient Analytics | MedInsight", layout="wide", page_icon="👤")
css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{open(css_path).read()}</style>", unsafe_allow_html=True)

st.markdown("# 👤 Patient Analytics")
filters = render_sidebar_filters()
where, params = build_where_clause(filters)

# ── Demographics ──────────────────────────────────────────────────────────────

st.markdown("### Patient Demographics")

demo_sql = """
SELECT
    gender,
    age_band,
    city,
    insurance_status,
    risk_category,
    engagement_level,
    churn_risk,
    COUNT(*) AS patients
FROM analytics.dim_patients
GROUP BY 1,2,3,4,5,6,7
"""
demo = query(demo_sql)

if not demo.empty:
    col1, col2, col3 = st.columns(3)
    with col1:
        gender_df = demo.groupby("gender")["patients"].sum().reset_index()
        fig = pie_chart(gender_df, "patients", "gender", "Gender Distribution", height=300)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        age_df = demo.groupby("age_band")["patients"].sum().reset_index()
        fig = bar_chart(age_df, "age_band", "patients", "Age Band Distribution", height=300)
        st.plotly_chart(fig, use_container_width=True)
    with col3:
        ins_df = demo.groupby("insurance_status")["patients"].sum().reset_index()
        fig = pie_chart(ins_df, "patients", "insurance_status", "Insurance Type", height=300)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        risk_df = demo.groupby("risk_category")["patients"].sum().reset_index()
        fig = pie_chart(risk_df, "patients", "risk_category", "Risk Category", height=300)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        eng_df = demo.groupby("engagement_level")["patients"].sum().reset_index()
        fig = bar_chart(eng_df, "engagement_level", "patients", "Engagement Level", height=300)
        st.plotly_chart(fig, use_container_width=True)
    with col3:
        churn_df = demo.groupby("churn_risk")["patients"].sum().reset_index()
        fig = pie_chart(churn_df, "patients", "churn_risk", "Churn Risk", height=300)
        st.plotly_chart(fig, use_container_width=True)

# ── Geography ─────────────────────────────────────────────────────────────────

st.markdown("### Patient Geography")
geo_sql = """
SELECT city, COUNT(*) AS patients, SUM(lifetime_value) AS total_ltv,
       ROUND(AVG(total_visits)::numeric, 1) AS avg_visits
FROM analytics.dim_patients
GROUP BY 1 ORDER BY patients DESC
"""
geo_df = query(geo_sql)
if not geo_df.empty:
    col1, col2 = st.columns(2)
    with col1:
        fig = bar_chart(geo_df, "city", "patients", "Patients by City", height=350)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = bar_chart(geo_df, "city", "total_ltv", "Total LTV by City (RON)", height=350)
        st.plotly_chart(fig, use_container_width=True)

# ── Cohort Retention ──────────────────────────────────────────────────────────

st.markdown("### Cohort Retention Analysis")
cohort_sql = """
SELECT
    TO_CHAR(cohort_month, 'YYYY-MM') AS cohort,
    period_number,
    retention_rate
FROM analytics.fct_patient_retention
WHERE period_number <= 12
ORDER BY cohort_month, period_number
"""
cohort_df = query(cohort_sql)
if not cohort_df.empty:
    pivot = cohort_df.pivot_table(
        index="cohort", columns="period_number",
        values="retention_rate", fill_value=0
    )
    fig = heatmap(pivot, "Patient Cohort Retention Rates", height=450)
    st.plotly_chart(fig, use_container_width=True)

# ── Patient LTV Distribution ──────────────────────────────────────────────────

st.markdown("### Patient Lifetime Value (LTV)")
ltv_sql = """
SELECT
    engagement_level,
    churn_risk,
    ROUND(AVG(lifetime_value), 0)    AS avg_ltv,
    ROUND(AVG(total_visits), 1)      AS avg_visits,
    COUNT(*)                         AS patients
FROM analytics.dim_patients
WHERE total_visits > 0
GROUP BY 1, 2
ORDER BY avg_ltv DESC
"""
ltv_df = query(ltv_sql)
if not ltv_df.empty:
    col1, col2 = st.columns(2)
    with col1:
        fig = bar_chart(ltv_df, "engagement_level", "avg_ltv",
                        "Avg LTV by Engagement Level (RON)", height=350)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = scatter_chart(
            ltv_df, x="avg_visits", y="avg_ltv", color="churn_risk",
            size="patients",
            title="Avg Visits vs. LTV by Churn Risk", height=350
        )
        st.plotly_chart(fig, use_container_width=True)

# ── Chronic Conditions ────────────────────────────────────────────────────────

st.markdown("### Chronic Conditions")
chronic_sql = """
SELECT
    UNNEST(STRING_TO_ARRAY(chronic_conditions, '; ')) AS condition,
    COUNT(*) AS patients
FROM analytics.dim_patients
WHERE chronic_conditions IS NOT NULL AND chronic_conditions != ''
GROUP BY 1
ORDER BY patients DESC
LIMIT 15
"""
chronic_df = query(chronic_sql)
if not chronic_df.empty:
    fig = bar_chart(chronic_df, "condition", "patients",
                    "Top Chronic Conditions", orientation="h", height=400)
    st.plotly_chart(fig, use_container_width=True)

st.download_button("Export Patient Data CSV", demo.to_csv(index=False) if not demo.empty else "",
                   "patient_analytics.csv", "text/csv")
