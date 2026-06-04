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

# Brand header
st.markdown("""
<div class="brand-header">
    <div class="brand-title">🏥 MedInsight Analytics Platform</div>
    <div class="brand-subtitle">Enterprise Healthcare Analytics — Romania Private Clinic Network</div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
### Welcome to MedInsight Analytics Platform

This platform provides executive-grade analytics for a Romanian private healthcare network
operating clinics in **Cluj-Napoca, București, Timișoara, Iași, Brașov,** and **Constanța**.

---

#### Navigate using the sidebar pages:

| Page | Description |
|------|-------------|
| 📊 **Executive Overview** | Revenue KPIs, appointments, YoY growth, clinic comparison |
| 👨‍⚕️ **Doctor Performance** | Rankings, utilization, ratings, revenue contribution |
| 👤 **Patient Analytics** | Demographics, retention, cohorts, LTV segmentation |
| 💰 **Financial Analytics** | Revenue trends, profitability, payment methods |
| ⚙️ **Operational Metrics** | Cancellations, no-shows, wait times, peak hours |
| 🔮 **Predictive Analytics** | Forecasts, churn risk, no-show prediction |

---
""")

col1, col2, col3 = st.columns(3)
with col1:
    st.info("**Data Period**: Jan 2023 – Dec 2024")
with col2:
    st.info("**Coverage**: 6 Clinics | 50 Doctors | 5,000 Patients")
with col3:
    st.info("**Tech Stack**: PostgreSQL · dbt · Python · Streamlit")
