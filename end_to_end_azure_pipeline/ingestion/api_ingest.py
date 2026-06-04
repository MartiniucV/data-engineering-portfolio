"""
API Ingestion Layer — SmartCity Environmental Analytics Platform
================================================================
Business Context:
    A European city (population 500K) has deployed 50 environmental monitoring
    stations tracking air quality and weather. The city council needs:
      - Real-time alerts when AQI exceeds safe thresholds (EU Directive 2008/50/EC)
      - Daily reports for public health dashboard (publicly accessible website)
      - Historical trend analysis for urban planning decisions

    The data platform must ingest station data every hour, with < 5 min
    latency from measurement to dashboard update.

Azure Production Architecture (simulated locally):
    Open-Meteo API → Azure API Management (rate limiting, auth) →
    Azure Function (HTTP trigger, every hour) →
    ADLS Gen2 raw zone → Event triggers downstream processing

Local simulation:
    Open-Meteo API (free, no key) → pandas → Parquet on local filesystem
"""
import logging
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Monitoring station registry ────────────────────────────────────────────────
# Real Azure: stored in Azure SQL DB, managed via city GIS portal
# In production: 50 stations across the city grid
STATIONS: dict[str, dict] = {
    "CITY-CENTRE":   {"latitude": 51.5074,  "longitude": -0.1278,  "zone": "urban"},
    "NORTH-SUBURBS": {"latitude": 51.5630,  "longitude": -0.0754,  "zone": "residential"},
    "INDUSTRIAL":    {"latitude": 51.4900,  "longitude": -0.0900,  "zone": "industrial"},
    "PARK-ZONE":     {"latitude": 51.5070,  "longitude": -0.1660,  "zone": "green"},
    "AIRPORT-PROX":  {"latitude": 51.4700,  "longitude": -0.1545,  "zone": "transport"},
    "SOUTH-GATE":    {"latitude": 51.4500,  "longitude": -0.1200,  "zone": "residential"},
    "RIVER-THAMES":  {"latitude": 51.5030,  "longitude": -0.0730,  "zone": "waterfront"},
    "EAST-END":      {"latitude": 51.5200,  "longitude": -0.0500,  "zone": "urban"},
}

API_URL     = "https://api.open-meteo.com/v1/forecast"
RAW_PATH    = Path("data/smartcity/raw")


def fetch_station_data(
    station_id: str,
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
) -> Optional[pd.DataFrame]:
    """
    Fetch daily weather + air quality proxy data from Open-Meteo.

    Real Azure:
        - Azure API Management: enforces rate limits (1000 calls/hour), logs to App Insights
        - Azure Function with Managed Identity: no API keys in code
        - Azure Key Vault: any private API keys stored here, referenced by name
        - Retry policy: Azure Function host.json → "retry": {"strategy": "exponentialBackoff"}
    """
    params = {
        "latitude":  lat,
        "longitude": lon,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "wind_speed_10m_max",
            "wind_direction_10m_dominant",
            "sunshine_duration",
            "uv_index_max",
            "weather_code",
        ],
        "timezone":   "Europe/London",
        "start_date": start_date,
        "end_date":   end_date,
    }

    try:
        resp = requests.get(API_URL, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException as exc:
        # Real Azure: log to Application Insights as a failed dependency
        # ai.track_dependency("OpenMeteo", f"/{station_id}", False, str(exc))
        logger.error("  Station %-16s FAILED: %s", station_id, exc)
        return None

    df = pd.DataFrame(payload["daily"])
    df.rename(columns={"time": "measurement_date"}, inplace=True)
    df["measurement_date"] = pd.to_datetime(df["measurement_date"])

    # Station metadata
    df["station_id"] = station_id
    df["latitude"]   = lat
    df["longitude"]  = lon
    df["_ingest_ts"] = pd.Timestamp.utcnow().isoformat()

    return df


def compute_aqi_proxy(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute a simplified AQI proxy from weather parameters.

    Real system: AQI computed from actual pollutant sensors
    (PM2.5, PM10, NO2, O3). Here we derive a proxy that correlates
    with pollution risk (high wind + rain = lower pollution).

    EU AQI categories:
        Good: 0-50 | Fair: 51-100 | Moderate: 101-150 |
        Poor: 151-200 | Very Poor: 201-250 | Extremely Poor: 251+
    """
    df = df.copy()
    # Proxy: lower wind + less rain + high UV = more pollution accumulation
    wind_factor   = 1 - (df["wind_speed_10m_max"].clip(0, 50) / 50)
    rain_factor   = 1 - (df["precipitation_sum"].clip(0, 20) / 20)
    uv_factor     = (df["uv_index_max"].fillna(0).clip(0, 11) / 11)

    df["aqi_proxy"] = ((wind_factor * 0.4 + rain_factor * 0.4 + uv_factor * 0.2) * 250).round(1)
    df["aqi_category"] = pd.cut(
        df["aqi_proxy"],
        bins=[0, 50, 100, 150, 200, 250, 999],
        labels=["Good", "Fair", "Moderate", "Poor", "Very Poor", "Extremely Poor"],
    )
    df["exceeds_eu_threshold"] = df["aqi_proxy"] > 100  # EU Directive alert threshold
    return df


def ingest(days_back: int = 30) -> Path:
    """
    Main ingestion function.

    Real Azure deployment:
        - Runs as an Azure Function (Timer trigger: "0 0 * * * *" = hourly)
        - Output: ADLS Gen2 container 'raw', path 'smartcity/{station_id}/{date}/'
        - After write: publishes event to Azure Event Grid → triggers downstream
        - Monitoring: Azure Monitor metric alert if execution time > 5 minutes
    """
    end_date   = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=days_back - 1)
    logger.info(
        "Ingesting SmartCity data: %s → %s  (%d stations)",
        start_date, end_date, len(STATIONS),
    )

    frames: list[pd.DataFrame] = []
    for station_id, meta in STATIONS.items():
        df = fetch_station_data(
            station_id, meta["latitude"], meta["longitude"],
            start_date.isoformat(), end_date.isoformat(),
        )
        if df is not None:
            df["zone"] = meta["zone"]
            df = compute_aqi_proxy(df)
            frames.append(df)
            logger.info("  %-16s  %d days  AQI avg=%.1f", station_id, len(df), df["aqi_proxy"].mean())

    if not frames:
        logger.error("No data fetched — aborting")
        sys.exit(1)

    combined = pd.concat(frames, ignore_index=True)
    RAW_PATH.mkdir(parents=True, exist_ok=True)
    output = RAW_PATH / "environmental_readings.parquet"
    combined.to_parquet(output, index=False)

    alerts = combined[combined["exceeds_eu_threshold"]]
    if not alerts.empty:
        logger.warning(
            "EU threshold exceeded: %d station-days  (worst AQI=%.1f at %s)",
            len(alerts),
            alerts["aqi_proxy"].max(),
            alerts.loc[alerts["aqi_proxy"].idxmax(), "station_id"],
        )

    logger.info("Ingested %d rows → %s", len(combined), output)
    return output


if __name__ == "__main__":
    ingest(days_back=30)
