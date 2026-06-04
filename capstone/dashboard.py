"""
Streamlit dashboard for the weather data platform.
Run with: streamlit run dashboard.py
"""
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine

DB_URL = "postgresql://vlad:vlad123@localhost:5432/portfolio"
TABLE = "weather_daily"

st.set_page_config(
    page_title="Weather Data Platform",
    page_icon="🌤",
    layout="wide",
)

WEATHER_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Icy fog", 51: "Light drizzle", 53: "Drizzle",
    55: "Heavy drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 80: "Rain showers",
    85: "Snow showers", 95: "Thunderstorm", 99: "Hail thunderstorm",
}


@st.cache_data(ttl=300)
def load_data() -> pd.DataFrame:
    engine = create_engine(DB_URL)
    df = pd.read_sql(f"SELECT * FROM {TABLE} ORDER BY date", engine)
    df["date"] = pd.to_datetime(df["date"])
    df["weather_description"] = df["weather_code"].map(WEATHER_CODES).fillna("Unknown")
    return df


def main() -> None:
    st.title("🌤 Weather Data Platform — Global Cities")
    st.caption("Source: Open-Meteo API · Refreshes every 5 min · Data loaded via ingest.py → transform.py")

    try:
        df = load_data()
    except Exception as exc:
        st.error(f"Database connection failed: {exc}")
        st.code("python ingest.py && python transform.py", language="bash")
        st.info("Run the commands above to populate the database, then refresh.")
        return

    # ── Sidebar ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("Filters")
        all_cities = sorted(df["city"].unique())
        selected = st.multiselect("Cities", all_cities, default=all_cities)

        min_d, max_d = df["date"].min().date(), df["date"].max().date()
        date_range = st.date_input("Date range", value=[min_d, max_d], min_value=min_d, max_value=max_d)

    filt = df[df["city"].isin(selected)]
    if len(date_range) == 2:
        filt = filt[
            (filt["date"] >= pd.Timestamp(date_range[0]))
            & (filt["date"] <= pd.Timestamp(date_range[1]))
        ]

    if filt.empty:
        st.warning("No data for the current filter selection.")
        return

    # ── KPIs ───────────────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Records", f"{len(filt):,}")
    c2.metric("Avg Max Temp", f"{filt['temperature_2m_max'].mean():.1f} °C")
    c3.metric("Avg Min Temp", f"{filt['temperature_2m_min'].mean():.1f} °C")
    c4.metric("Avg Precipitation", f"{filt['precipitation_sum'].mean():.1f} mm")
    c5.metric("Avg Wind Speed", f"{filt['wind_speed_10m_max'].mean():.1f} km/h")

    st.divider()

    # ── Temperature trends ─────────────────────────────────────────────────────
    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Daily Max Temperature by City (°C)")
        temp_pivot = filt.pivot_table(index="date", columns="city", values="temperature_2m_max")
        st.line_chart(temp_pivot, use_container_width=True)

    with col_r:
        st.subheader("Daily Precipitation by City (mm)")
        precip_pivot = filt.pivot_table(
            index="date", columns="city", values="precipitation_sum", aggfunc="sum"
        )
        st.bar_chart(precip_pivot, use_container_width=True)

    st.divider()

    # ── City summary table ─────────────────────────────────────────────────────
    st.subheader("City Summary Statistics")
    summary = (
        filt.groupby("city", as_index=False)
        .agg(
            avg_max_temp=("temperature_2m_max", "mean"),
            avg_min_temp=("temperature_2m_min", "mean"),
            avg_temp_range=("temp_range", "mean"),
            total_precipitation=("precipitation_sum", "sum"),
            avg_wind_speed=("wind_speed_10m_max", "mean"),
            days_of_data=("date", "nunique"),
        )
        .round(2)
    )
    summary.columns = [
        "City", "Avg Max (°C)", "Avg Min (°C)",
        "Avg Range (°C)", "Total Precip (mm)",
        "Avg Wind (km/h)", "Days",
    ]
    st.dataframe(summary, use_container_width=True, hide_index=True)

    # ── Wind speed chart ───────────────────────────────────────────────────────
    st.subheader("Daily Max Wind Speed by City (km/h)")
    wind_pivot = filt.pivot_table(index="date", columns="city", values="wind_speed_10m_max")
    st.area_chart(wind_pivot, use_container_width=True)

    # ── Raw data ───────────────────────────────────────────────────────────────
    with st.expander("Raw data table"):
        st.dataframe(
            filt.sort_values("date", ascending=False).reset_index(drop=True),
            use_container_width=True,
        )


if __name__ == "__main__":
    main()
