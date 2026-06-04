"""MedInsight - Doctor Performance"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from dashboard.components.db import query
from dashboard.components.charts import bar_chart, scatter_chart, heatmap, gauge_chart
from dashboard.components.filters import render_sidebar_filters, build_where_clause
from dashboard.components.kpi_cards import kpi_card, kpi_row, section_header, brand_header

st.set_page_config(page_title="Doctor Performance · MedInsight", layout="wide", page_icon="👨‍⚕️")
css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

brand_header("Doctor Performance Analytics")
filters = render_sidebar_filters()
where, params = build_where_clause(filters)

doc_sql = f"""
SELECT doctor_name, specialty,
       COUNT(*) AS appointments,
       SUM(net_revenue) AS revenue,
       ROUND(AVG(rating) FILTER (WHERE rating IS NOT NULL)::numeric,2) AS avg_rating,
       ROUND(COUNT(*) FILTER (WHERE is_completed)::numeric/NULLIF(COUNT(*),0)*100,1) AS completion_pct,
       ROUND(AVG(waiting_time_minutes)::numeric,1) AS avg_wait,
       COUNT(DISTINCT patient_id) AS unique_patients
FROM analytics.fct_appointments {where}
GROUP BY doctor_name, specialty ORDER BY revenue DESC
"""
doc_df = query(doc_sql, **params)

if doc_df.empty:
    st.warning("No data for selected filters.")
    st.stop()

section_header("Network Summary", "📊")
kpi_row([
    kpi_card("🩺", "Doctors Active",    f"{len(doc_df):,}",                    accent="red"),
    kpi_card("💰", "Avg Revenue/Doctor",f"RON {doc_df['revenue'].mean():,.0f}", accent="teal"),
    kpi_card("⭐", "Network Avg Rating", f"{doc_df['avg_rating'].mean():.2f}",  accent="gold"),
    kpi_card("✅", "Avg Completion",     f"{doc_df['completion_pct'].mean():.1f}%", accent="blue"),
])

# ── Utilization gauges (top 3 by revenue) ────────────────────────────────────
section_header("Top Doctor Utilization", "🎯")
top3 = doc_df.head(3)
cols = st.columns(3)
for col, (_, row) in zip(cols, top3.iterrows()):
    with col:
        fig = gauge_chart(float(row["completion_pct"] or 0), 100,
                          f"{row['doctor_name'][:25]}", height=220)
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"{row['specialty']} · RON {float(row['revenue'] or 0):,.0f}")

# ── Ranking table ─────────────────────────────────────────────────────────────
section_header("Full Doctor Ranking", "📋")
top_n = st.slider("Show top N", 10, min(200, len(doc_df)), 25)
display_df = doc_df.head(top_n).reset_index(drop=True)
display_df.index += 1
display_df["revenue"] = display_df["revenue"].apply(lambda x: f"RON {float(x):,.0f}" if pd.notna(x) else "-")
st.dataframe(display_df, use_container_width=True, height=380)

# ── Revenue vs Rating scatter ─────────────────────────────────────────────────
section_header("Revenue vs. Patient Satisfaction", "💡")
col1, col2 = st.columns(2)
with col1:
    raw = query(doc_sql, **params)  # un-formatted copy
    st.plotly_chart(
        scatter_chart(raw, "avg_rating", "revenue", "specialty", "appointments",
                      ["doctor_name","completion_pct"], "Revenue vs. Rating", 400),
        use_container_width=True,
    )
with col2:
    st.plotly_chart(
        bar_chart(doc_df.head(15), "doctor_name", "appointments",
                  "Top 15 by Appointments", orientation="h", height=400),
        use_container_width=True,
    )

# ── Specialty analysis ────────────────────────────────────────────────────────
section_header("Specialty Breakdown", "🔬")
spec_sql = f"""
SELECT specialty,
       COUNT(DISTINCT doctor_name)                                         AS doctors,
       COUNT(*)                                                            AS appointments,
       SUM(net_revenue)                                                    AS revenue,
       ROUND(AVG(rating) FILTER(WHERE rating IS NOT NULL)::numeric,2)     AS avg_rating,
       ROUND(COUNT(*) FILTER(WHERE is_completed)::numeric/NULLIF(COUNT(*),0)*100,1) AS completion_pct
FROM analytics.fct_appointments {where}
GROUP BY 1 ORDER BY revenue DESC
"""
sdf = query(spec_sql, **params)
if not sdf.empty:
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(bar_chart(sdf,"specialty","revenue","Revenue by Specialty",orientation="h",height=380),
                        use_container_width=True)
    with col2:
        st.plotly_chart(bar_chart(sdf,"specialty","completion_pct","Completion Rate (%)",orientation="h",height=380),
                        use_container_width=True)

# ── Heatmap ───────────────────────────────────────────────────────────────────
section_header("Appointment Load Heatmap", "🗓️")
heat_sql = f"""
SELECT TRIM(day_of_week) AS dow, appointment_hour AS hour, COUNT(*) AS cnt
FROM analytics.fct_appointments {where}
GROUP BY 1,2
"""
hdf = query(heat_sql, **params)
if not hdf.empty:
    dow_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    hdf["dow"] = pd.Categorical(hdf["dow"].str.strip(), categories=dow_order, ordered=True)
    pivot = hdf.pivot_table(index="dow", columns="hour", values="cnt", fill_value=0)
    pivot = pivot.reindex([d for d in dow_order if d in pivot.index])
    st.plotly_chart(heatmap(pivot,"Appointment Volume: Day × Hour",350), use_container_width=True)

st.download_button("⬇ Export Rankings", doc_df.to_csv(index=False), "doctor_performance.csv","text/csv")
