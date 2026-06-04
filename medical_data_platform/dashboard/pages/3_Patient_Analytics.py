"""MedInsight - Patient Analytics"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from dashboard.components.db import query
from dashboard.components.charts import bar_chart, pie_chart, scatter_chart, heatmap
from dashboard.components.filters import render_sidebar_filters, build_where_clause
from dashboard.components.kpi_cards import kpi_card, kpi_row, section_header, brand_header, insight_banner

st.set_page_config(page_title="Patient Analytics · MedInsight", layout="wide", page_icon="👤")
css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

brand_header("Patient Intelligence Center")
filters = render_sidebar_filters()
where, params = build_where_clause(filters)

# ── Patient KPIs ──────────────────────────────────────────────────────────────
pat_kpi = query("""
    SELECT COUNT(*) AS total,
           COUNT(*) FILTER (WHERE total_visits > 0) AS active,
           COUNT(*) FILTER (WHERE churn_risk = 'High') AS high_churn,
           ROUND(AVG(lifetime_value)::numeric,0) AS avg_ltv,
           COUNT(*) FILTER (WHERE has_chronic_condition) AS chronic
    FROM analytics.dim_patients
""")
if not pat_kpi.empty:
    r = pat_kpi.iloc[0]
    total  = int(r["total"] or 0)
    active = int(r["active"] or 0)
    churn  = int(r["high_churn"] or 0)
    ltv    = float(r["avg_ltv"] or 0)
    chronic = int(r["chronic"] or 0)
    kpi_row([
        kpi_card("👥", "Total Patients",    f"{total:,}",   accent="teal"),
        kpi_card("🟢", "Active Patients",   f"{active:,}",  accent="blue"),
        kpi_card("⚠️", "High Churn Risk",   f"{churn:,}",   f"{churn/total*100:.1f}% of total" if total else None, False, "red"),
        kpi_card("💰", "Avg Patient LTV",   f"RON {ltv:,.0f}", accent="gold"),
        kpi_card("💊", "With Chronic Cond.",f"{chronic:,}", accent="red"),
    ])
    if churn / total > 0.25 if total else False:
        insight_banner(f"{churn/total*100:.1f}% of patients at high churn risk — activate retention campaigns.")

# ── Demographics ──────────────────────────────────────────────────────────────
section_header("Demographics", "👥")
demo = query("""
    SELECT gender, age_band, city, insurance_status, risk_category,
           engagement_level, churn_risk, COUNT(*) AS patients
    FROM analytics.dim_patients GROUP BY 1,2,3,4,5,6,7
""")
if not demo.empty:
    col1, col2, col3 = st.columns(3)
    with col1:
        gdf = demo.groupby("gender")["patients"].sum().reset_index()
        st.plotly_chart(pie_chart(gdf,"patients","gender","Gender Split",300), use_container_width=True)
    with col2:
        adf = demo.groupby("age_band")["patients"].sum().reset_index()
        st.plotly_chart(bar_chart(adf,"age_band","patients","Age Band",height=300), use_container_width=True)
    with col3:
        idf = demo.groupby("insurance_status")["patients"].sum().reset_index()
        st.plotly_chart(pie_chart(idf,"patients","insurance_status","Insurance Type",300), use_container_width=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        rdf = demo.groupby("risk_category")["patients"].sum().reset_index()
        st.plotly_chart(pie_chart(rdf,"patients","risk_category","Risk Category",300), use_container_width=True)
    with col2:
        edf = demo.groupby("engagement_level")["patients"].sum().reset_index()
        st.plotly_chart(bar_chart(edf,"engagement_level","patients","Engagement Level",height=300), use_container_width=True)
    with col3:
        cdf = demo.groupby("churn_risk")["patients"].sum().reset_index()
        st.plotly_chart(pie_chart(cdf,"patients","churn_risk","Churn Risk",300), use_container_width=True)

# ── Geography ─────────────────────────────────────────────────────────────────
section_header("Geographic Distribution", "🗺️")
geo = query("""
    SELECT city, COUNT(*) AS patients, SUM(lifetime_value) AS total_ltv,
           ROUND(AVG(total_visits)::numeric,1) AS avg_visits
    FROM analytics.dim_patients GROUP BY 1 ORDER BY patients DESC LIMIT 20
""")
if not geo.empty:
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(bar_chart(geo,"city","patients","Patients by City",height=380), use_container_width=True)
    with col2:
        st.plotly_chart(bar_chart(geo,"city","total_ltv","Total LTV by City (RON)",height=380), use_container_width=True)

# ── Cohort retention ──────────────────────────────────────────────────────────
section_header("Cohort Retention Analysis", "📅")
cohort = query("""
    SELECT TO_CHAR(cohort_month,'YYYY-MM') AS cohort, period_number, retention_rate
    FROM analytics.fct_patient_retention WHERE period_number <= 12
    ORDER BY cohort_month, period_number
""")
if not cohort.empty:
    pivot = cohort.pivot_table(index="cohort",columns="period_number",values="retention_rate",fill_value=0)
    st.plotly_chart(heatmap(pivot,"Patient Cohort Retention Rates (Month 0–12)",450), use_container_width=True)

# ── LTV scatter ───────────────────────────────────────────────────────────────
section_header("Lifetime Value vs. Engagement", "💡")
ltv = query("""
    SELECT engagement_level, churn_risk,
           ROUND(AVG(lifetime_value)::numeric,0) AS avg_ltv,
           ROUND(AVG(total_visits)::numeric,1) AS avg_visits,
           COUNT(*) AS patients
    FROM analytics.dim_patients WHERE total_visits > 0 GROUP BY 1,2 ORDER BY avg_ltv DESC
""")
if not ltv.empty:
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(bar_chart(ltv,"engagement_level","avg_ltv","Avg LTV by Engagement (RON)",height=340),
                        use_container_width=True)
    with col2:
        st.plotly_chart(scatter_chart(ltv,"avg_visits","avg_ltv","churn_risk","patients",
                                      title="Visits vs. LTV by Churn Risk",height=340),
                        use_container_width=True)

# ── Chronic conditions ────────────────────────────────────────────────────────
section_header("Top Chronic Conditions", "💊")
chronic = query("""
    SELECT UNNEST(STRING_TO_ARRAY(chronic_conditions,'; ')) AS condition, COUNT(*) AS patients
    FROM analytics.dim_patients WHERE chronic_conditions IS NOT NULL AND chronic_conditions <> ''
    GROUP BY 1 ORDER BY patients DESC LIMIT 15
""")
if not chronic.empty:
    st.plotly_chart(bar_chart(chronic,"condition","patients","Chronic Condition Prevalence",
                              orientation="h",height=420), use_container_width=True)

st.download_button("⬇ Export Demographics", demo.to_csv(index=False) if not demo.empty else "",
                   "patient_demographics.csv","text/csv")
