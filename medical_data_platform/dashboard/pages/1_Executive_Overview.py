"""MedInsight - Executive Overview"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from dashboard.components.db import query
from dashboard.components.charts import line_chart, bar_chart, pie_chart, area_chart
from dashboard.components.filters import render_sidebar_filters, build_where_clause
from dashboard.components.kpi_cards import kpi_card, kpi_row, section_header, brand_header, insight_banner

st.set_page_config(page_title="Executive Overview · MedInsight", layout="wide", page_icon="📊")
css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

brand_header("Executive Command Center")
filters = render_sidebar_filters()
where, params = build_where_clause(filters)

# ── KPI row ──────────────────────────────────────────────────────────────────
kpi_sql = f"""
SELECT
    COUNT(DISTINCT appointment_id)                                                  AS total_appts,
    COUNT(DISTINCT patient_id)                                                      AS active_patients,
    COALESCE(SUM(net_revenue), 0)                                                   AS total_revenue,
    COUNT(DISTINCT doctor_id)                                                       AS active_doctors,
    ROUND(COALESCE(AVG(net_revenue) FILTER (WHERE is_completed), 0)::numeric, 0)   AS avg_revenue,
    ROUND(COUNT(*) FILTER (WHERE is_completed)::numeric / NULLIF(COUNT(*),0)*100,1) AS completion_pct
FROM analytics.fct_appointments {where}
"""
kpi = query(kpi_sql, **params)

prev_sql = f"""
SELECT COALESCE(SUM(net_revenue),0) AS prev_rev, COUNT(*) AS prev_appts
FROM analytics.fct_appointments
WHERE appointment_date >= '{filters["start_date"]}'::date - INTERVAL '1 year'
  AND appointment_date <  '{filters["start_date"]}'::date
"""
prev = query(prev_sql)

if not kpi.empty:
    r = kpi.iloc[0]
    rev   = float(r["total_revenue"] or 0)
    appts = int(r["total_appts"] or 0)
    pats  = int(r["active_patients"] or 0)
    docs  = int(r["active_doctors"] or 0)
    avg_r = float(r["avg_revenue"] or 0)
    comp  = float(r["completion_pct"] or 0)

    prev_rev   = float(prev.iloc[0]["prev_rev"] or 1) if not prev.empty else 1
    prev_appts = int(prev.iloc[0]["prev_appts"] or 1) if not prev.empty else 1
    rev_yoy  = f"{(rev/prev_rev - 1)*100:+.1f}% YoY" if prev_rev else None
    appt_yoy = f"{(appts/prev_appts - 1)*100:+.1f}% YoY" if prev_appts else None
    rev_up   = rev > prev_rev

    kpi_row([
        kpi_card("💰", "Total Revenue",      f"RON {rev:,.0f}",  rev_yoy,  rev_up,   "red"),
        kpi_card("📅", "Appointments",       f"{appts:,}",       appt_yoy, appts > prev_appts, "teal"),
        kpi_card("👤", "Active Patients",    f"{pats:,}",        accent="blue"),
        kpi_card("🩺", "Active Doctors",     f"{docs:,}",        accent="gold"),
        kpi_card("💊", "Avg Revenue/Appt",   f"RON {avg_r:,.0f}", accent="teal"),
        kpi_card("✅", "Completion Rate",    f"{comp:.1f}%",     accent="red"),
    ])

    if comp < 68:
        insight_banner(f"Completion rate {comp:.1f}% is below the 70% network target. Review cancellation drivers.")

st.markdown("---")

# ── Revenue trend ─────────────────────────────────────────────────────────────
section_header("Revenue Trend", "📈")
col1, col2 = st.columns([2, 1])
with col1:
    df = query(f"""
        SELECT TO_CHAR(appointment_date,'YYYY-MM') AS month,
               SUM(net_revenue) AS revenue, COUNT(*) AS appointments
        FROM analytics.fct_appointments {where}
        GROUP BY 1 ORDER BY 1
    """, **params)
    if not df.empty:
        st.plotly_chart(area_chart(df,"month","revenue","Monthly Net Revenue (RON)",height=340),
                        use_container_width=True)
with col2:
    df2 = query(f"SELECT status, COUNT(*) AS cnt FROM analytics.fct_appointments {where} GROUP BY 1", **params)
    if not df2.empty:
        st.plotly_chart(pie_chart(df2,"cnt","status","Appointment Status Mix",height=340),
                        use_container_width=True)

# ── Clinic comparison ──────────────────────────────────────────────────────────
section_header("Clinic Performance Leaderboard", "🏆")
clinic_sql = f"""
SELECT clinic_city,
       COUNT(*) AS appointments, SUM(net_revenue) AS revenue,
       ROUND(AVG(rating) FILTER (WHERE rating IS NOT NULL)::numeric, 2) AS avg_rating,
       ROUND(COUNT(*) FILTER (WHERE is_completed)::numeric/NULLIF(COUNT(*),0)*100,1) AS completion_pct
FROM analytics.fct_appointments {where}
GROUP BY 1 ORDER BY revenue DESC
"""
cdf = query(clinic_sql, **params)
if not cdf.empty:
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(bar_chart(cdf,"clinic_city","revenue","Revenue by Clinic (RON)",height=350),
                        use_container_width=True)
    with col2:
        st.plotly_chart(bar_chart(cdf,"clinic_city","appointments","Appointments by Clinic",height=350),
                        use_container_width=True)

# ── Specialty revenue ─────────────────────────────────────────────────────────
section_header("Revenue by Specialty", "🔬")
sdf = query(f"""
    SELECT specialty, SUM(net_revenue) AS revenue, COUNT(*) AS appointments
    FROM analytics.fct_appointments {where}
    GROUP BY 1 ORDER BY revenue DESC
""", **params)
if not sdf.empty:
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(bar_chart(sdf,"specialty","revenue","Revenue by Specialty",orientation="h",height=400),
                        use_container_width=True)
    with col2:
        st.plotly_chart(pie_chart(sdf,"revenue","specialty","Revenue Mix",height=400),
                        use_container_width=True)

if not cdf.empty:
    st.download_button("⬇ Export Clinic Summary", cdf.to_csv(index=False), "clinic_summary.csv","text/csv")
