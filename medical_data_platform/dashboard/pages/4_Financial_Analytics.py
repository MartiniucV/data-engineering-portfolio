"""MedInsight - Financial Analytics"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from dashboard.components.db import query
from dashboard.components.charts import bar_chart, pie_chart, line_chart, area_chart
from dashboard.components.filters import render_sidebar_filters, build_where_clause
from dashboard.components.kpi_cards import kpi_card, kpi_row, section_header, brand_header

st.set_page_config(page_title="Financial Analytics · MedInsight", layout="wide", page_icon="💰")
css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

brand_header("Financial Performance Center")
filters = render_sidebar_filters()
where, params = build_where_clause(filters)

# ── Financial KPIs ────────────────────────────────────────────────────────────
fin = query(f"""
SELECT
    COALESCE(SUM(net_revenue),0)                                                   AS net_revenue,
    COALESCE(SUM(insurance_reimbursement),0)                                       AS reimbursements,
    COALESCE(SUM(actual_price),0)                                                  AS gross_revenue,
    COALESCE(SUM(actual_price) - SUM(net_revenue), 0)                              AS discounts,
    ROUND(COALESCE(AVG(net_revenue) FILTER(WHERE is_completed),0)::numeric,0)      AS avg_invoice,
    COUNT(DISTINCT appointment_date)                                                AS rev_days
FROM analytics.fct_appointments {where}
""", **params)

if not fin.empty:
    r = fin.iloc[0]
    kpi_row([
        kpi_card("💵","Net Revenue",      f"RON {float(r['net_revenue'] or 0):,.0f}",     accent="red"),
        kpi_card("📋","Gross Revenue",    f"RON {float(r['gross_revenue'] or 0):,.0f}",   accent="teal"),
        kpi_card("🏥","Reimbursements",   f"RON {float(r['reimbursements'] or 0):,.0f}",  accent="blue"),
        kpi_card("🏷️","Discounts Given",  f"RON {float(r['discounts'] or 0):,.0f}",       accent="gold"),
        kpi_card("🧾","Avg Invoice",      f"RON {float(r['avg_invoice'] or 0):,.0f}",     accent="teal"),
        kpi_card("📆","Revenue Days",     f"{int(r['rev_days'] or 0):,}",                 accent="blue"),
    ])

st.markdown("---")

# ── Monthly trend ─────────────────────────────────────────────────────────────
section_header("Monthly Revenue Breakdown", "📈")
monthly = query(f"""
    SELECT TO_CHAR(appointment_date,'YYYY-MM') AS month,
           SUM(net_revenue) AS net_revenue,
           SUM(insurance_reimbursement) AS reimbursements,
           SUM(actual_price) AS gross_revenue
    FROM analytics.fct_appointments {where}
    GROUP BY 1 ORDER BY 1
""", **params)
if not monthly.empty:
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(area_chart(monthly,"month",["net_revenue","gross_revenue"],
                                   "Revenue Trend (RON)",height=360), use_container_width=True)
    with col2:
        st.plotly_chart(line_chart(monthly,"month","reimbursements",
                                   "Insurance Reimbursements (RON)",height=360), use_container_width=True)

# ── Specialty & clinic revenue ────────────────────────────────────────────────
section_header("Revenue by Specialty & Clinic", "🏥")
col1, col2 = st.columns(2)
with col1:
    sdf = query(f"""
        SELECT specialty, SUM(net_revenue) AS revenue
        FROM analytics.fct_appointments {where}
        GROUP BY 1 ORDER BY revenue DESC
    """, **params)
    if not sdf.empty:
        st.plotly_chart(bar_chart(sdf,"specialty","revenue","Revenue by Specialty",
                                  orientation="h",height=380), use_container_width=True)
with col2:
    cdf = query(f"""
        SELECT clinic_city AS city, SUM(net_revenue) AS revenue
        FROM analytics.fct_appointments {where}
        GROUP BY 1 ORDER BY revenue DESC LIMIT 15
    """, **params)
    if not cdf.empty:
        st.plotly_chart(bar_chart(cdf,"city","revenue","Revenue by City",height=380),
                        use_container_width=True)

# ── Service profitability ─────────────────────────────────────────────────────
section_header("Service Profitability", "📊")
svc = query(f"""
    SELECT service_name, service_category,
           COUNT(*) AS appointments,
           SUM(net_revenue) AS total_revenue,
           ROUND(AVG(net_revenue)::numeric,0) AS avg_revenue,
           ROUND(AVG(profitability_margin)*100::numeric,1) AS margin_pct
    FROM analytics.fct_appointments {where}
    GROUP BY service_name, service_category ORDER BY total_revenue DESC LIMIT 16
""", **params)
if not svc.empty:
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(bar_chart(svc,"service_name","total_revenue","Revenue by Service",
                                  orientation="h",height=440), use_container_width=True)
    with col2:
        st.plotly_chart(bar_chart(svc,"service_name","margin_pct","Profitability Margin (%)",
                                  orientation="h",height=440), use_container_width=True)

# ── Payment methods ───────────────────────────────────────────────────────────
section_header("Payment Methods", "💳")
pay = query(f"""
    SELECT payment_method, COUNT(*) AS transactions, SUM(net_revenue) AS revenue
    FROM analytics.fct_appointments {where} AND payment_method IS NOT NULL
    GROUP BY 1 ORDER BY revenue DESC
""", **params)
if not pay.empty:
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(pie_chart(pay,"transactions","payment_method","Transaction Volume",350),
                        use_container_width=True)
    with col2:
        st.plotly_chart(pie_chart(pay,"revenue","payment_method","Revenue Share",350),
                        use_container_width=True)

if not svc.empty:
    st.download_button("⬇ Export Service Revenue", svc.to_csv(index=False),"service_revenue.csv","text/csv")
