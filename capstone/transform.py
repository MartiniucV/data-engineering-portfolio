"""
Reads the raw weather Parquet produced by ingest.py, applies cleaning and
feature engineering, then loads the result into PostgreSQL.
"""
import logging
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

PARQUET_PATH = Path("data/weather_raw.parquet")
DB_URL = "postgresql://vlad:vlad123@localhost:5432/portfolio"
TABLE = "weather_daily"

DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    id                   SERIAL PRIMARY KEY,
    date                 DATE        NOT NULL,
    city                 TEXT        NOT NULL,
    latitude             DOUBLE PRECISION,
    longitude            DOUBLE PRECISION,
    temperature_2m_max   DOUBLE PRECISION,
    temperature_2m_min   DOUBLE PRECISION,
    precipitation_sum    DOUBLE PRECISION,
    wind_speed_10m_max   DOUBLE PRECISION,
    weather_code         INTEGER,
    temp_range           DOUBLE PRECISION,
    loaded_at            TIMESTAMP   NOT NULL DEFAULT NOW(),
    UNIQUE (date, city)
)
"""


def load_parquet() -> pd.DataFrame:
    if not PARQUET_PATH.exists():
        logger.error("Parquet file not found at %s — run ingest.py first", PARQUET_PATH)
        sys.exit(1)
    df = pd.read_parquet(PARQUET_PATH)
    logger.info("Loaded %d raw rows from %s", len(df), PARQUET_PATH)
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)

    df = df.dropna(subset=["date", "city", "temperature_2m_max", "temperature_2m_min"])
    after_nulls = len(df)

    # Physical temperature bounds: −80 °C to +60 °C
    valid_temp = (
        df["temperature_2m_max"].between(-80, 60)
        & df["temperature_2m_min"].between(-80, 60)
        & (df["temperature_2m_max"] >= df["temperature_2m_min"])
    )
    df = df[valid_temp]

    # Non-negative weather quantities
    df["precipitation_sum"] = df["precipitation_sum"].clip(lower=0).fillna(0)
    df["wind_speed_10m_max"] = df["wind_speed_10m_max"].clip(lower=0).fillna(0)

    # Derived feature
    df["temp_range"] = df["temperature_2m_max"] - df["temperature_2m_min"]

    df["date"] = pd.to_datetime(df["date"])

    logger.info(
        "Cleaning: %d → %d rows (dropped %d nulls, %d out-of-range)",
        before, len(df), before - after_nulls, after_nulls - len(df),
    )
    return df.reset_index(drop=True)


def load_postgres(df: pd.DataFrame) -> None:
    engine = create_engine(DB_URL, future=True)

    with engine.begin() as conn:
        conn.execute(text(DDL))
        conn.execute(text(f"TRUNCATE TABLE {TABLE} RESTART IDENTITY"))

    write_cols = [
        "date", "city", "latitude", "longitude",
        "temperature_2m_max", "temperature_2m_min",
        "precipitation_sum", "wind_speed_10m_max",
        "weather_code", "temp_range",
    ]
    df[write_cols].to_sql(
        TABLE, engine,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=500,
    )
    logger.info("Loaded %d rows into PostgreSQL table '%s'", len(df), TABLE)


def transform() -> pd.DataFrame:
    df = load_parquet()
    df = clean(df)
    load_postgres(df)
    return df


if __name__ == "__main__":
    transform()
