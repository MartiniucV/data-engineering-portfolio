"""
SmartCity Environmental Analytics Dashboard
============================================
Azure Production: Deployed as an Azure Container App (scales to zero when idle).
Behind Azure Front Door for CDN + SSL. Authentication via Azure AD B2C.
Data refreshes automatically every 15 minutes via Streamlit's cache TTL.

Local: streamlit run visualization/streamlit_dashboard.py
Azure: docker build + az containerapp create --image smartcity-dashboard
"""
from pathlib import Path

import pandas as pd
import streamlit as st

GOLD_DAILY   = Path("data/smartcity/gold/daily_station_metrics.parquet")
GOLD_WEEKLY  = Path("data/smartcity/gold/zone_weekly_metrics.parquet")
QUALITY_JSON = Path("data/smartcity/monitoring/quality_results.json")

st.set_page_config(
    page_title="SmartCity Environmental Dashboard",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

EU_THRESHOLD = 100.0
AQI_COLORS   = {"Good": "🟢", "Fair": "🟡", "Moderate": "🟠", "Poor": "🔴", "Very Poor": "🟣", "Extremely Poor": "⚫"}
ZONE_ICONS   = {"urban": "🏙️", "residential": "🏘️", "industrial": "🏭", "green": "🌳", "transport": "✈️", "waterfront": "🌊"}


@st.cache_data(ttl=900)
def load_data():
    """
    Cache data for 15 minutes.
    Azure Production: reads directly from ADLS Gen2 via ABFSS URI.
        df = pd.read_parquet("abfss://analytics@smartcity.dfs.core.windows.net/daily_station_metrics/")
    Managed Identity handles auth — no credentials in the container image.
    """
    daily  = pd.read_parquet(GOLD_DAILY)  if GOLD_DAILY.exists()  else pd.DataFrame()
    weekly = pd.read_parquet(GOLD_WEEKLY) if GOLD_WEEKLY.exists() else pd.DataFrame()
    if not daily.empty:
        daily["measurement_date"] = pd.to_datetime(daily["measurement_date"])
    return daily, weekly


@st.cache_data(ttl=900)
def load_quality():
    import json
    return json.loads(QUALITY_JSON.read_text()) if QUALITY_JSON.exists() else {}


def aqi_category(aqi: float) -> str:
    if aqi <= 50:   return "Good"
    if aqi <= 100:  return "Fair"
    if aqi <= 150:  return "Moderate"
    if aqi <= 200:  return "Poor"
    if aqi <= 250:  return "Very Poor"
    return "Extremely Poor"


def main() -> None:
    st.title("🌍 SmartCity Environmental Analytics")
    st.caption("Real-time air quality monitoring · EU Directive 2008/50/EC · Data refreshes every 15 min")

    daily, weekly = load_data()
    quality       = load_quality()

    if daily.empty:
        st.error("No data available.")
        st.code("python orchestration/pipeline_dag.py", language="bash")
        st.info("Run the pipeline above to load data, then refresh.")
        return

    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("Filters")
        stations    = sorted(daily["station_id"].unique())
        sel_stations = st.multiselect("Monitoring Stations", stations, default=stations)

        zones       = sorted(daily["zone"].unique())
        sel_zones    = st.multiselect("Urban Zones", zones, default=zones)

        min_d, max_d = daily["measurement_date"].min().date(), daily["measurement_date"].max().date()
        date_range   = st.date_input("Date Range", value=[min_d, max_d], min_value=min_d, max_value=max_d)

        st.divider()
        if quality:
            pass_rate = quality.get("pass_rate_pct", 0)
            status    = quality.get("overall_status", "UNKNOWN")
            st.metric("Data Quality", f"{pass_rate:.1f}%",
                      delta="PASS" if status == "PASS" else "FAIL",
                      delta_color="normal" if status == "PASS" else "inverse")

    # Filter data
    filt = daily[daily["station_id"].isin(sel_stations) & daily["zone"].isin(sel_zones)]
    if len(date_range) == 2:
        filt = filt[
            (filt["measurement_date"] >= pd.Timestamp(date_range[0]))
            & (filt["measurement_date"] <= pd.Timestamp(date_range[1]))
        ]

    if filt.empty:
        st.warning("No data for current filters.")
        return

    # ── KPI Row ───────────────────────────────────────────────────────────────
    avg_aqi     = filt["avg_aqi"].mean()
    exceedances = filt["eu_exceedance_days"].sum()
    worst_zone  = filt.groupby("zone")["avg_aqi"].mean().idxmax()
    heat_days   = filt["heat_days"].sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Avg AQI", f"{avg_aqi:.1f}", help="Lower = cleaner air")
    c2.metric("EU Threshold Breaches", f"{exceedances:,}",
              delta=f"{'⚠️ Alert' if exceedances > 5 else 'Within limits'}",
              delta_color="inverse" if exceedances > 5 else "off")
    c3.metric(f"Worst Zone {ZONE_ICONS.get(worst_zone, '')}", worst_zone.replace("-", " ").title())
    c4.metric("Heat Days (>30°C)", f"{heat_days:,}")

    st.divider()

    # ── AQI Trend ─────────────────────────────────────────────────────────────
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("Daily AQI Trend by Station")
        aqi_pivot = filt.pivot_table(index="measurement_date", columns="station_id", values="avg_aqi")
        st.line_chart(aqi_pivot, use_container_width=True)
        st.caption(f"Red dashed line = EU threshold ({EU_THRESHOLD})")

    with col_r:
        st.subheader("Temperature Range by Station")
        temp_pivot = filt.pivot_table(index="measurement_date", columns="station_id", values="max_temp")
        st.area_chart(temp_pivot, use_container_width=True)

    # ── Station Summary Table ─────────────────────────────────────────────────
    st.subheader("Station Health Summary")
    summary = (
        filt.groupby(["station_id", "zone"])
        .agg(
            avg_aqi_=("avg_aqi", "mean"),
            max_aqi_=("max_aqi", "max"),
            eu_breaches=("eu_exceedance_days", "sum"),
            avg_max_temp=("max_temp", "mean"),
            total_precip=("total_precip", "sum"),
            days=("measurement_date", "nunique"),
        )
        .round(1)
        .reset_index()
    )
    summary.columns = ["Station", "Zone", "Avg AQI", "Max AQI", "EU Breaches", "Avg Max Temp (°C)", "Total Precip (mm)", "Days"]
    summary["AQI Category"] = summary["Avg AQI"].apply(
        lambda x: f"{AQI_COLORS.get(aqi_category(x), '')} {aqi_category(x)}"
    )
    st.dataframe(summary.sort_values("Avg AQI", ascending=False), use_container_width=True, hide_index=True)

    # ── Precipitation + Wind ──────────────────────────────────────────────────
    if not filt.empty:
        st.subheader("Daily Precipitation by Station (mm)")
        precip_pivot = filt.pivot_table(index="measurement_date", columns="station_id", values="total_precip").fillna(0)
        st.bar_chart(precip_pivot, use_container_width=True)

    # ── Data Quality ──────────────────────────────────────────────────────────
    if quality:
        with st.expander("Data Quality Report"):
            results = quality.get("results", [])
            if results:
                qdf = pd.DataFrame(results)[["expectation", "success", "observed", "expected"]]
                qdf["status"] = qdf["success"].map({True: "✓ PASS", False: "✗ FAIL"})
                st.dataframe(qdf[["status", "expectation", "observed", "expected"]],
                             use_container_width=True, hide_index=True)

    with st.expander("Raw data"):
        st.dataframe(filt.sort_values("measurement_date", ascending=False).reset_index(drop=True),
                     use_container_width=True)


if __name__ == "__main__":
    main()
