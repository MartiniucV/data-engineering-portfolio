"""MedInsight - Predictive Analytics"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from dashboard.components.db import query
from dashboard.components.charts import bar_chart, scatter_chart, apply_dark_layout
from dashboard.components.filters import render_sidebar_filters, build_where_clause
from dashboard.components.kpi_cards import kpi_card, kpi_row, section_header, brand_header, insight_banner

st.set_page_config(page_title="Predictive Analytics · MedInsight", layout="wide", page_icon="🔮")
css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

brand_header("Predictive Intelligence & AI Insights")
st.caption("Models trained on 2020–2024 historical data. Forecasts are indicative estimates.")
filters = render_sidebar_filters()
where, params = build_where_clause(filters)

# ── Forecast ──────────────────────────────────────────────────────────────────
section_header("Revenue Forecast — Next 6 Months", "📈")

@st.cache_data(ttl=600)
def revenue_forecast():
    hist = query("""
        SELECT TO_CHAR(revenue_date,'YYYY-MM') AS month, SUM(net_revenue) AS revenue
        FROM analytics.fct_daily_revenue GROUP BY 1 ORDER BY 1
    """)
    if hist.empty or len(hist) < 6:
        return hist, pd.DataFrame()
    vals  = hist["revenue"].astype(float).values
    x     = np.arange(len(vals))
    coeff = np.polyfit(x, vals, 1)
    trend = np.polyval(coeff, x)
    seasonal = vals - trend
    sp = np.concatenate([seasonal, np.zeros(12 - len(seasonal) % 12)])
    sp_pat = sp.reshape(-1, 12).mean(axis=0)
    fx   = np.arange(len(vals), len(vals) + 6)
    ft   = np.polyval(coeff, fx)
    fs   = sp_pat[fx % 12]
    fcast= (ft + fs).clip(min=0)
    conf = fcast * 0.10
    last = pd.Period(hist["month"].iloc[-1], freq="M")
    fm   = [str(last + i + 1) for i in range(6)]
    return hist, pd.DataFrame({"month": fm, "forecast": fcast, "lower": fcast-conf, "upper": fcast+conf})

hist_df, fc_df = revenue_forecast()
if not hist_df.empty:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hist_df["month"], y=hist_df["revenue"].astype(float),
        name="Historical", line=dict(color="#d63031", width=2.5),
        fill="tozeroy", fillcolor="rgba(214,48,49,0.06)",
    ))
    if not fc_df.empty:
        fig.add_trace(go.Scatter(
            x=fc_df["month"], y=fc_df["forecast"],
            name="Forecast", line=dict(color="#00d4aa", width=2.5, dash="dot"),
        ))
        fig.add_trace(go.Scatter(
            x=list(fc_df["month"]) + list(fc_df["month"])[::-1],
            y=list(fc_df["upper"]) + list(fc_df["lower"])[::-1],
            fill="toself", fillcolor="rgba(0,212,170,0.10)",
            line=dict(color="rgba(0,0,0,0)"), name="Confidence Band",
        ))
    apply_dark_layout(fig, "Revenue Forecast — Historical + 6-Month Projection (RON)", height=420)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ── No-show risk factors ──────────────────────────────────────────────────────
section_header("No-Show Risk Analysis", "🚫")
noshw = query("""
    SELECT channel, TRIM(day_of_week) AS dow, urgency_level,
           ROUND(COUNT(*) FILTER(WHERE is_no_show)::numeric/NULLIF(COUNT(*),0)*100,1) AS noshw_rate,
           COUNT(*) AS total
    FROM analytics.fct_appointments GROUP BY 1,2,3
""")
col1, col2 = st.columns(2)
if not noshw.empty:
    with col1:
        ch = noshw.groupby("channel")["noshw_rate"].mean().reset_index().sort_values("noshw_rate")
        st.plotly_chart(bar_chart(ch,"channel","noshw_rate","No-Show Rate by Channel (%)",
                                  orientation="h",height=320), use_container_width=True)
    with col2:
        dow_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        dow = noshw.groupby("dow")["noshw_rate"].mean().reset_index()
        dow["dow"] = pd.Categorical(dow["dow"].str.strip(), categories=dow_order, ordered=True)
        dow = dow.sort_values("dow")
        st.plotly_chart(bar_chart(dow,"dow","noshw_rate","No-Show Rate by Day (%)",height=320),
                        use_container_width=True)

# ── Churn risk ────────────────────────────────────────────────────────────────
section_header("Patient Churn Risk Distribution", "⚠️")
churn = query("""
    SELECT churn_risk, engagement_level, COUNT(*) AS patients,
           ROUND(AVG(lifetime_value)::numeric,0) AS avg_ltv,
           ROUND(AVG(days_since_last_visit)::numeric,0) AS avg_days_inactive
    FROM analytics.dim_patients GROUP BY 1,2 ORDER BY avg_ltv DESC
""")
if not churn.empty:
    total_c = churn["patients"].sum()
    high_c  = int(churn[churn["churn_risk"]=="High"]["patients"].sum())
    kpi_row([
        kpi_card("🔴","High Churn Patients",  f"{high_c:,}",
                 f"{high_c/total_c*100:.1f}% of network", False, "red"),
        kpi_card("🟡","Medium Churn Patients",
                 f"{int(churn[churn['churn_risk']=='Medium']['patients'].sum()):,}", accent="gold"),
        kpi_card("🟢","Low Risk Patients",
                 f"{int(churn[churn['churn_risk']=='Low']['patients'].sum()):,}", accent="teal"),
    ])
    if high_c / total_c > 0.25:
        insight_banner(f"Churn alert: {high_c/total_c*100:.1f}% of patients at high risk. Activate SMS re-engagement campaign.")

    col1, col2 = st.columns(2)
    with col1:
        cs = churn.groupby("churn_risk")[["patients","avg_ltv"]].agg(
            patients=("patients","sum"), avg_ltv=("avg_ltv","mean")
        ).reset_index()
        st.plotly_chart(bar_chart(cs,"churn_risk","patients","Patients by Churn Risk",height=320),
                        use_container_width=True)
    with col2:
        st.plotly_chart(scatter_chart(churn,"avg_days_inactive","avg_ltv","churn_risk","patients",
                                      title="Inactivity vs. LTV by Churn Risk",height=320),
                        use_container_width=True)
    st.dataframe(churn.sort_values("avg_ltv",ascending=False), use_container_width=True)

# ── Doctor utilisation ────────────────────────────────────────────────────────
section_header("Doctor Utilization Analysis", "🩺")
util = query("""
    SELECT full_name, specialty, completion_rate, no_show_rate,
           total_revenue, unique_patients, performance_tier
    FROM analytics.dim_doctors WHERE total_appointments > 0
    ORDER BY completion_rate DESC LIMIT 25
""")
if not util.empty:
    st.plotly_chart(scatter_chart(
        util,"completion_rate","total_revenue","specialty","unique_patients",
        ["full_name","no_show_rate","performance_tier"],
        "Doctor Utilization: Completion Rate vs. Revenue",450
    ), use_container_width=True)

# ── Anomaly detection summary ─────────────────────────────────────────────────
section_header("Billing Anomaly Indicators", "🔍")
anom = query("""
    SELECT TO_CHAR(revenue_date,'YYYY-MM') AS month, city, SUM(net_revenue) AS revenue,
           ROUND(AVG(avg_invoice_value)::numeric,0) AS avg_invoice
    FROM analytics.fct_daily_revenue GROUP BY 1,2 ORDER BY 1,2
""")
if not anom.empty:
    overall_mean = float(anom["avg_invoice"].mean())
    overall_std  = float(anom["avg_invoice"].std())
    anom["zscore"]     = ((anom["avg_invoice"] - overall_mean) / max(overall_std, 1)).round(2)
    anom["is_anomaly"] = anom["zscore"].abs() > 2.5
    anomalies = anom[anom["is_anomaly"]]
    kpi_row([
        kpi_card("⚠️","Anomalous Months Detected", str(len(anomalies)), accent="red"),
        kpi_card("📊","Avg Invoice (Network)",      f"RON {overall_mean:,.0f}", accent="teal"),
    ])
    if not anomalies.empty:
        st.dataframe(anomalies[["month","city","avg_invoice","zscore"]].sort_values("zscore",ascending=False),
                     use_container_width=True)
