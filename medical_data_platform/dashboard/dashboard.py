"""
MedInsight Analytics Platform - Main Dashboard Entry Point
Streamlit multi-page application with dark healthcare theme.
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

st.set_page_config(
    page_title="MedInsight Analytics Platform",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load custom CSS
css_path = Path(__file__).parent / "assets" / "style.css"
if css_path.exists():
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from components.kpi_cards import brand_header, kpi_card, kpi_row

brand_header("Romanian Private Healthcare Network — Enterprise Analytics")

st.markdown("""
<div style="margin:28px 0 20px;">
  <p style="font-size:1.05rem;color:#e8edf3;font-weight:600;margin-bottom:6px;">
    MedInsight Analytics Platform
  </p>
  <p style="color:#7d8da8;font-size:0.88rem;line-height:1.7;">
    A production-grade data platform centralising clinical, financial, and operational
    intelligence for a 60-clinic network across Romania.
    Built with <strong style="color:#e8edf3;">PostgreSQL · dbt · Python · Streamlit</strong>.
  </p>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="section-title">Platform Navigation</div>', unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("""
    **📊 Executive Overview**
    Revenue KPIs, YoY growth, clinic leaderboard, specialty mix

    **👨‍⚕️ Doctor Performance**
    Rankings, utilization gauges, rating analysis, heatmaps
    """)
with col2:
    st.markdown("""
    **👤 Patient Analytics**
    Demographics, cohort retention, LTV, churn, geography

    **💰 Financial Analytics**
    Revenue trends, service profitability, payment methods
    """)
with col3:
    st.markdown("""
    **⚙️ Operational Metrics**
    Cancellations, no-shows, wait times, occupancy gauges

    **🔮 Predictive Analytics**
    Revenue forecast, churn AI, no-show risk, anomaly detection
    """)

st.markdown("---")
kpi_row([
    kpi_card("🏥", "Clinic Network",  "60 Clinics",    "6 Regions of Romania", True, "red"),
    kpi_card("🩺", "Medical Staff",   "500 Doctors",   "10 Specialties",       True, "teal"),
    kpi_card("👤", "Patients",        "500,000",        "2020 – 2024",          True, "blue"),
    kpi_card("📅", "Appointments",    "2,000,000+",    "5 Years of Data",      True, "gold"),
])
