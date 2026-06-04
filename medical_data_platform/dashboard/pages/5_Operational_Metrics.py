"""MedInsight - Operational Metrics"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from dashboard.components.db import query
from dashboard.components.charts import bar_chart, line_chart, heatmap, pie_chart, area_chart, gauge_chart
from dashboard.components.filters import render_sidebar_filters, build_where_clause
from dashboard.components.kpi_cards import kpi_card, kpi_row, section_header, brand_header, insight_banner

st.set_page_config(page_title="Operational Metrics · MedInsight", layout="wide", page_icon="⚙️")
css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

brand_header("Operational Intelligence Center")
filters = render_sidebar_filters()
where, params = build_where_clause(filters)

# ── Ops KPIs ──────────────────────────────────────────────────────────────────
ops = query(f"""
SELECT
    ROUND(COUNT(*) FILTER(WHERE is_cancelled)::numeric/NULLIF(COUNT(*),0)*100,2) AS cancel_rate,
    ROUND(COUNT(*) FILTER(WHERE is_no_show)::numeric  /NULLIF(COUNT(*),0)*100,2) AS noshw_rate,
    ROUND(AVG(waiting_time_minutes)::numeric,1)                                   AS avg_wait,
    MAX(waiting_time_minutes)                                                     AS max_wait,
    ROUND(AVG(consultation_duration_minutes) FILTER(WHERE is_completed)::numeric,1) AS avg_consult,
    COUNT(DISTINCT appointment_date)                                              AS op_days
FROM analytics.fct_appointments {where}
""", **params)

if not ops.empty:
    r = ops.iloc[0]
    cancel = float(r["cancel_rate"] or 0)
    noshw  = float(r["noshw_rate"] or 0)
    wait   = float(r["avg_wait"] or 0)

    kpi_row([
        kpi_card("❌", "Cancellation Rate", f"{cancel:.1f}%", accent="red"),
        kpi_card("🚫", "No-Show Rate",      f"{noshw:.1f}%",  accent="red"),
        kpi_card("⏱️", "Avg Wait Time",     f"{wait:.0f} min", accent="gold"),
        kpi_card("⏳", "Max Wait Time",     f"{int(r['max_wait'] or 0)} min", accent="teal"),
        kpi_card("🩺", "Avg Consult",       f"{float(r['avg_consult'] or 0):.0f} min", accent="blue"),
        kpi_card("📅", "Operating Days",    f"{int(r['op_days'] or 0):,}", accent="teal"),
    ])

    if cancel + noshw > 25:
        insight_banner(f"Combined disruption rate {cancel+noshw:.1f}% (cancellations + no-shows) exceeds 25% threshold.")

# ── Operational gauges ────────────────────────────────────────────────────────
section_header("Network Health Gauges", "🎯")
col1, col2, col3 = st.columns(3)
if not ops.empty:
    r = ops.iloc[0]
    completion = 100 - float(r["cancel_rate"] or 0) - float(r["noshw_rate"] or 0)
    with col1:
        st.plotly_chart(gauge_chart(completion, 100, "Completion Rate (%)", 220), use_container_width=True)
    with col2:
        st.plotly_chart(gauge_chart(max(0, 60 - float(r["avg_wait"] or 0)), 60, "Wait Time Score", 220),
                        use_container_width=True)
    with col3:
        st.plotly_chart(gauge_chart(max(0, 100 - float(r["noshw_rate"] or 0)), 100, "Show-Up Rate (%)", 220),
                        use_container_width=True)

st.markdown("---")

# ── Volume trend ──────────────────────────────────────────────────────────────
section_header("Appointment Volume Trend", "📈")
vol = query(f"""
    SELECT TO_CHAR(appointment_date,'YYYY-MM') AS month,
           COUNT(*) AS total,
           COUNT(*) FILTER(WHERE is_completed) AS completed,
           COUNT(*) FILTER(WHERE is_cancelled) AS cancelled,
           COUNT(*) FILTER(WHERE is_no_show)   AS no_shows
    FROM analytics.fct_appointments {where} GROUP BY 1 ORDER BY 1
""", **params)
if not vol.empty:
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(area_chart(vol,"month",["completed","cancelled","no_shows"],
                                   "Monthly Volume by Status",380), use_container_width=True)
    with col2:
        rate = query(f"""
            SELECT TO_CHAR(appointment_date,'YYYY-MM') AS month,
                   ROUND(COUNT(*) FILTER(WHERE is_cancelled)::numeric/NULLIF(COUNT(*),0)*100,1) AS cancel_pct,
                   ROUND(COUNT(*) FILTER(WHERE is_no_show)::numeric  /NULLIF(COUNT(*),0)*100,1) AS noshw_pct
            FROM analytics.fct_appointments {where} GROUP BY 1 ORDER BY 1
        """, **params)
        if not rate.empty:
            st.plotly_chart(line_chart(rate,"month",["cancel_pct","noshw_pct"],
                                       "Disruption Rates (%)",height=380), use_container_width=True)

# ── Cancellation reasons ──────────────────────────────────────────────────────
section_header("Cancellation & No-Show Drivers", "🔍")
col1, col2 = st.columns(2)
with col1:
    canc = query(f"""
        SELECT cancellation_reason, COUNT(*) AS cnt
        FROM analytics.fct_appointments {where} AND cancellation_reason IS NOT NULL
        GROUP BY 1 ORDER BY cnt DESC
    """, **params)
    if not canc.empty:
        st.plotly_chart(bar_chart(canc,"cancellation_reason","cnt","Cancellation Reasons",
                                  orientation="h",height=360), use_container_width=True)
with col2:
    ch = query(f"""
        SELECT channel,
               ROUND(COUNT(*) FILTER(WHERE is_no_show)::numeric/NULLIF(COUNT(*),0)*100,1) AS noshw_rate,
               COUNT(*) AS total
        FROM analytics.fct_appointments {where} GROUP BY 1 ORDER BY noshw_rate DESC
    """, **params)
    if not ch.empty:
        st.plotly_chart(bar_chart(ch,"channel","noshw_rate","No-Show Rate by Channel (%)",height=360),
                        use_container_width=True)

# ── Wait time heatmap ─────────────────────────────────────────────────────────
section_header("Wait Time: Day × Hour Heatmap", "⏱️")
wait_df = query(f"""
    SELECT TRIM(day_of_week) AS dow, appointment_hour AS hour,
           ROUND(AVG(waiting_time_minutes)::numeric,1) AS avg_wait
    FROM analytics.fct_appointments {where} AND waiting_time_minutes IS NOT NULL
    GROUP BY 1,2
""", **params)
if not wait_df.empty:
    dow_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    wait_df["dow"] = pd.Categorical(wait_df["dow"].str.strip(), categories=dow_order, ordered=True)
    pivot = wait_df.pivot_table(index="dow",columns="hour",values="avg_wait",fill_value=0)
    pivot = pivot.reindex([d for d in dow_order if d in pivot.index])
    st.plotly_chart(heatmap(pivot,"Average Wait Time (min): Day × Hour",360), use_container_width=True)

# ── Channel & urgency mix ─────────────────────────────────────────────────────
section_header("Booking Channel & Urgency Mix", "📱")
col1, col2 = st.columns(2)
with col1:
    urg = query(f"SELECT urgency_level, COUNT(*) AS cnt FROM analytics.fct_appointments {where} GROUP BY 1", **params)
    if not urg.empty:
        st.plotly_chart(pie_chart(urg,"cnt","urgency_level","Urgency Level",300), use_container_width=True)
with col2:
    chmix = query(f"SELECT channel, COUNT(*) AS cnt FROM analytics.fct_appointments {where} GROUP BY 1", **params)
    if not chmix.empty:
        st.plotly_chart(pie_chart(chmix,"cnt","channel","Booking Channel",300), use_container_width=True)
