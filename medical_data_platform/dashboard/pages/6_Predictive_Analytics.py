"""
MedInsight - Page 6: Predictive Analytics
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from dashboard.components.db import query
from dashboard.components.charts import line_chart, bar_chart, scatter_chart, apply_dark_layout
from dashboard.components.filters import render_sidebar_filters, build_where_clause

st.set_page_config(page_title="Predictive Analytics | MedInsight", layout="wide", page_icon="🔮")
css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{open(css_path).read()}</style>", unsafe_allow_html=True)

st.markdown("# 🔮 Predictive Analytics")
st.caption("Models trained on 2023–2024 historical data. Forecasts are indicative estimates.")
filters = render_sidebar_filters()


# ── Revenue Forecast ──────────────────────────────────────────────────────────

st.markdown("### Revenue Forecast (Next 6 Months)")

@st.cache_data(ttl=600)
def get_revenue_forecast():
    """Simple Holt-Winters-like forecast using numpy."""
    hist = query("""
        SELECT TO_CHAR(invoice_date, 'YYYY-MM') AS month, SUM(net_revenue) AS revenue
        FROM analytics.fct_daily_revenue
        GROUP BY 1 ORDER BY 1
    """)
    if hist.empty or len(hist) < 6:
        return hist, pd.DataFrame()

    revenue = hist["revenue"].astype(float).values
    months = hist["month"].tolist()

    # Simple linear + seasonal forecast
    x = np.arange(len(revenue))
    coeffs = np.polyfit(x, revenue, 1)
    trend_line = np.polyval(coeffs, x)
    seasonal = revenue - trend_line

    # Pad seasonal to multiples of 12
    pad = 12 - (len(seasonal) % 12)
    seasonal_padded = np.concatenate([seasonal, np.zeros(pad)])
    seasonal_pattern = seasonal_padded.reshape(-1, 12).mean(axis=0)

    # Forecast 6 months
    forecast_x = np.arange(len(revenue), len(revenue) + 6)
    trend_forecast = np.polyval(coeffs, forecast_x)
    seasonal_forecast = seasonal_pattern[forecast_x % 12]
    point_forecast = (trend_forecast + seasonal_forecast).clip(min=0)
    uncertainty = point_forecast * 0.10

    # Build future month labels
    last_month = pd.Period(months[-1], freq="M")
    future_months = [str(last_month + i + 1) for i in range(6)]

    forecast_df = pd.DataFrame({
        "month": future_months,
        "forecast": point_forecast,
        "lower": point_forecast - uncertainty,
        "upper": point_forecast + uncertainty,
    })
    return hist, forecast_df

hist_df, fc_df = get_revenue_forecast()

if not hist_df.empty:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hist_df["month"], y=hist_df["revenue"].astype(float),
        name="Historical", line=dict(color="#00d4aa", width=2),
    ))
    if not fc_df.empty:
        fig.add_trace(go.Scatter(
            x=fc_df["month"], y=fc_df["forecast"],
            name="Forecast", line=dict(color="#58a6ff", width=2, dash="dash"),
        ))
        fig.add_trace(go.Scatter(
            x=list(fc_df["month"]) + list(fc_df["month"])[::-1],
            y=list(fc_df["upper"]) + list(fc_df["lower"])[::-1],
            fill="toself", fillcolor="rgba(88,166,255,0.15)",
            line=dict(color="rgba(0,0,0,0)"), name="Confidence Interval",
        ))
    apply_dark_layout(fig, "Revenue Forecast — Historical + 6-Month Projection", height=420)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ── No-Show Risk Factors ──────────────────────────────────────────────────────

st.markdown("### No-Show Risk Analysis")

noshw_sql = """
SELECT
    channel,
    urgency_level,
    TRIM(day_of_week) AS dow,
    appointment_hour,
    ROUND(COUNT(*) FILTER (WHERE is_no_show)::numeric / NULLIF(COUNT(*),0)*100, 1) AS no_show_rate,
    COUNT(*) AS total
FROM analytics.fct_appointments
GROUP BY channel, urgency_level, TRIM(day_of_week), appointment_hour
"""
noshw_df = query(noshw_sql)

col1, col2 = st.columns(2)
with col1:
    if not noshw_df.empty:
        ch_risk = noshw_df.groupby("channel")["no_show_rate"].mean().reset_index().sort_values("no_show_rate", ascending=True)
        fig = bar_chart(ch_risk, "channel", "no_show_rate",
                        "No-Show Rate by Channel (%)", orientation="h", height=320)
        st.plotly_chart(fig, use_container_width=True)
with col2:
    if not noshw_df.empty:
        dow_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        dow_risk = noshw_df.groupby("dow")["no_show_rate"].mean().reset_index()
        dow_risk["dow"] = pd.Categorical(dow_risk["dow"].str.strip(), categories=dow_order, ordered=True)
        dow_risk = dow_risk.sort_values("dow")
        fig = bar_chart(dow_risk, "dow", "no_show_rate",
                        "No-Show Rate by Day of Week (%)", height=320)
        st.plotly_chart(fig, use_container_width=True)

# ── Patient Churn Risk ────────────────────────────────────────────────────────

st.markdown("### Patient Churn Risk Distribution")

churn_sql = """
SELECT
    churn_risk,
    engagement_level,
    COUNT(*) AS patients,
    ROUND(AVG(lifetime_value),0) AS avg_ltv,
    ROUND(AVG(days_since_last_visit),0) AS avg_days_inactive
FROM analytics.dim_patients
GROUP BY 1, 2
ORDER BY churn_risk, engagement_level
"""
churn_df = query(churn_sql)

if not churn_df.empty:
    col1, col2 = st.columns(2)
    with col1:
        churn_sum = churn_df.groupby("churn_risk")[["patients", "avg_ltv"]].agg(
            patients=("patients", "sum"),
            avg_ltv=("avg_ltv", "mean")
        ).reset_index()
        fig = bar_chart(churn_sum, "churn_risk", "patients",
                        "Patients by Churn Risk", height=320)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = scatter_chart(
            churn_df,
            x="avg_days_inactive",
            y="avg_ltv",
            color="churn_risk",
            size="patients",
            title="Inactivity vs. LTV by Churn Risk",
            height=320,
        )
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        churn_df.sort_values("avg_ltv", ascending=False),
        use_container_width=True,
    )

# ── Doctor Utilization Forecast ───────────────────────────────────────────────

st.markdown("### Doctor Utilization Rates")

util_sql = """
SELECT
    full_name,
    specialty,
    completion_rate,
    no_show_rate,
    total_revenue,
    unique_patients,
    performance_tier
FROM analytics.dim_doctors
WHERE total_appointments > 0
ORDER BY completion_rate DESC
LIMIT 20
"""
util_df = query(util_sql)

if not util_df.empty:
    fig = scatter_chart(
        util_df,
        x="completion_rate",
        y="total_revenue",
        color="specialty",
        size="unique_patients",
        hover_data=["full_name", "no_show_rate", "performance_tier"],
        title="Doctor Utilization: Completion Rate vs. Revenue",
        height=450,
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Anomaly Detection Summary ────────────────────────────────────────────────

st.markdown("### Billing Anomaly Indicators")

anomaly_sql = """
SELECT
    TO_CHAR(invoice_date, 'YYYY-MM') AS month,
    city,
    SUM(net_revenue) AS revenue,
    COUNT(*) AS invoices,
    ROUND(AVG(net_revenue),2) AS avg_invoice
FROM analytics.fct_daily_revenue
GROUP BY 1, 2
ORDER BY 1, 2
"""
anom_df = query(anomaly_sql)

if not anom_df.empty:
    overall_mean = anom_df["avg_invoice"].mean()
    overall_std = anom_df["avg_invoice"].std()
    anom_df["zscore"] = ((anom_df["avg_invoice"] - overall_mean) / overall_std).round(2)
    anom_df["is_anomaly"] = anom_df["zscore"].abs() > 2.5

    anomalies = anom_df[anom_df["is_anomaly"]]
    st.metric("Detected Anomalous Months", len(anomalies))
    if not anomalies.empty:
        st.dataframe(anomalies[["month", "city", "avg_invoice", "zscore"]].sort_values("zscore", ascending=False),
                     use_container_width=True)
