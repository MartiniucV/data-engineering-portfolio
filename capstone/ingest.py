"""
Ingests daily weather data from the Open-Meteo API for five major cities and
persists the result as a Parquet file. No API key required.
"""
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

CITIES: dict[str, dict[str, float]] = {
    "New York":  {"latitude": 40.7128,  "longitude": -74.0060},
    "London":    {"latitude": 51.5074,  "longitude": -0.1278},
    "Tokyo":     {"latitude": 35.6762,  "longitude": 139.6503},
    "Sydney":    {"latitude": -33.8688, "longitude": 151.2093},
    "Sao Paulo": {"latitude": -23.5505, "longitude": -46.6333},
}

API_URL = "https://api.open-meteo.com/v1/forecast"
OUTPUT_PATH = Path("data/weather_raw.parquet")


def _fetch_city(city: str, lat: float, lon: float, start: str, end: str) -> pd.DataFrame:
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "wind_speed_10m_max",
            "weather_code",
        ],
        "timezone": "UTC",
        "start_date": start,
        "end_date": end,
    }
    resp = requests.get(API_URL, params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    df = pd.DataFrame(payload["daily"])
    df.rename(columns={"time": "date"}, inplace=True)
    df["date"] = pd.to_datetime(df["date"])
    df["city"] = city
    df["latitude"] = lat
    df["longitude"] = lon
    return df


def ingest(days_back: int = 90) -> Path:
    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=days_back - 1)
    start_str, end_str = start_date.isoformat(), end_date.isoformat()

    logger.info(
        "Fetching weather data %s → %s for %d cities",
        start_str, end_str, len(CITIES),
    )

    frames: list[pd.DataFrame] = []
    errors: list[str] = []

    for city, coords in CITIES.items():
        try:
            df = _fetch_city(city, coords["latitude"], coords["longitude"], start_str, end_str)
            frames.append(df)
            logger.info("  %-12s  %d rows fetched", city, len(df))
        except requests.RequestException as exc:
            logger.error("  %-12s  FAILED: %s", city, exc)
            errors.append(city)

    if not frames:
        logger.error("No data fetched — aborting")
        sys.exit(1)

    if errors:
        logger.warning("Skipped cities due to errors: %s", ", ".join(errors))

    combined = pd.concat(frames, ignore_index=True)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(OUTPUT_PATH, index=False)
    logger.info("Saved %d total rows to %s", len(combined), OUTPUT_PATH)
    return OUTPUT_PATH


if __name__ == "__main__":
    ingest()
