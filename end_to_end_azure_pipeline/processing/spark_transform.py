"""
Spark Processing Layer — SmartCity Environmental Analytics
==========================================================
Azure Production: Databricks cluster (DBR 14.x) running this job
on 3-node Standard_DS3_v2 cluster ($0.45/hr). Triggered by ADLS
file-arrival event after ingestion completes.

Local simulation: pandas mirrors PySpark DataFrame API patterns.
Every pandas operation has a PySpark comment showing the real equivalent.

PySpark-style coding conventions used throughout:
    - Functional transformation chains (avoid mutation)
    - Column expressions documented as SQL strings
    - Partition keys chosen for downstream query patterns
"""
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

RAW_PATH    = Path("data/smartcity/raw/environmental_readings.parquet")
SILVER_PATH = Path("data/smartcity/silver/readings_clean.parquet")
GOLD_PATH   = Path("data/smartcity/gold")

EU_ALERT_THRESHOLD = 100.0
TEMP_BOUNDS        = (-30.0, 55.0)


def load_bronze() -> pd.DataFrame:
    """
    Real Databricks:
        df = spark.read.format("delta")
                  .option("versionAsOf", 0)          # time travel
                  .load("abfss://raw@storage.dfs.core.windows.net/smartcity/")
        # OR with AutoLoader (incremental):
        df = spark.readStream.format("cloudFiles")
                  .option("cloudFiles.format", "parquet")
                  .option("checkpointLocation", checkpoint_path)
                  .load("abfss://raw@storage.dfs.core.windows.net/smartcity/")
    """
    if not RAW_PATH.exists():
        logger.error("Raw file not found. Run ingestion/api_ingest.py first.")
        raise FileNotFoundError(str(RAW_PATH))
    df = pd.read_parquet(RAW_PATH)
    df["measurement_date"] = pd.to_datetime(df["measurement_date"])
    logger.info("Bronze loaded: %d rows from %s", len(df), RAW_PATH)
    return df


def transform_silver(df: pd.DataFrame) -> pd.DataFrame:
    """
    Silver transformations — PySpark equivalent shown in comments.

    Real Databricks:
        from pyspark.sql import functions as F

        silver = (bronze
            .filter(F.col("temperature_2m_max").between(-30, 55))
            .filter(F.col("precipitation_sum") >= 0)
            .withColumn("temp_range",
                F.col("temperature_2m_max") - F.col("temperature_2m_min"))
            .withColumn("is_heat_day",
                F.col("temperature_2m_max") > F.lit(30.0))
            .withColumn("ingest_date",
                F.to_date(F.col("_ingest_ts")))
            .write.format("delta")
            .mode("overwrite")
            .partitionBy("station_id", "ingest_date")
            .saveAsTable("main.silver.environmental_readings")
        )
    """
    df = df.copy()

    # Quality filters
    initial = len(df)
    df = df[df["temperature_2m_max"].between(*TEMP_BOUNDS)]
    df = df[df["precipitation_sum"].fillna(0) >= 0]
    logger.info("Quality filters: %d → %d rows (dropped %d)", initial, len(df), initial - len(df))

    # Derived columns
    df["temp_range"]        = (df["temperature_2m_max"] - df["temperature_2m_min"]).round(2)
    df["is_heat_day"]       = df["temperature_2m_max"] > 30.0
    df["is_wet_day"]        = df["precipitation_sum"].fillna(0) > 5.0
    df["is_sunny_day"]      = df["sunshine_duration"].fillna(0) > 21600  # > 6 hours in seconds
    df["wind_beaufort"]     = pd.cut(
        df["wind_speed_10m_max"].fillna(0),
        bins=[0, 1, 5, 11, 19, 28, 38, 49, 61, 74, 88, 102, 117, 999],
        labels=range(13), right=False,
    ).astype(float).astype("Int64")
    df["ingest_date"]       = pd.to_datetime(df["_ingest_ts"], errors="coerce").dt.date
    df["_silver_ts"]        = datetime.utcnow().isoformat()

    # Partitioning note (real Delta write):
    # .partitionBy("station_id", "ingest_date") enables partition pruning
    # Queries like WHERE station_id='CITY-CENTRE' skip all other partitions
    SILVER_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(SILVER_PATH, index=False)
    logger.info("Silver written: %d rows → %s", len(df), SILVER_PATH)
    return df


def compute_gold_daily_station(silver: pd.DataFrame) -> pd.DataFrame:
    """
    Gold — daily metrics per station for public dashboard.

    Real Databricks post-hook:
        OPTIMIZE main.gold.daily_station_metrics ZORDER BY (measurement_date, station_id)
        -- After write, data skipping cuts date-range queries by ~85%
    """
    gold = (
        silver.groupby(["measurement_date", "station_id", "zone"])
        .agg(
            max_temp=("temperature_2m_max", "max"),
            min_temp=("temperature_2m_min", "min"),
            avg_temp=("temperature_2m_max", lambda x: ((x + silver.loc[x.index, "temperature_2m_min"]) / 2).mean()),
            total_precip=("precipitation_sum", "sum"),
            max_wind=("wind_speed_10m_max", "max"),
            avg_uv=("uv_index_max", "mean"),
            avg_aqi=("aqi_proxy", "mean"),
            max_aqi=("aqi_proxy", "max"),
            eu_exceedance_days=("exceeds_eu_threshold", "sum"),
            heat_days=("is_heat_day", "sum"),
            wet_days=("is_wet_day", "sum"),
        )
        .round(2)
        .reset_index()
    )
    gold["_gold_ts"] = datetime.utcnow().isoformat()
    return gold


def compute_gold_zone_weekly(silver: pd.DataFrame) -> pd.DataFrame:
    """
    Gold — weekly aggregates by urban zone for planning reports.
    Real Databricks: semantic model layer used by Power BI via Databricks SQL Warehouse.
    """
    silver["week"] = pd.to_datetime(silver["measurement_date"]).dt.to_period("W").astype(str)
    return (
        silver.groupby(["week", "zone"])
        .agg(
            avg_aqi=("aqi_proxy", "mean"),
            max_aqi=("aqi_proxy", "max"),
            total_exceedances=("exceeds_eu_threshold", "sum"),
            total_precipitation=("precipitation_sum", "sum"),
            avg_max_temp=("temperature_2m_max", "mean"),
        )
        .round(2)
        .reset_index()
    )


def run() -> None:
    bronze = load_bronze()
    silver = transform_silver(bronze)

    GOLD_PATH.mkdir(parents=True, exist_ok=True)

    daily_station = compute_gold_daily_station(silver)
    daily_station.to_parquet(GOLD_PATH / "daily_station_metrics.parquet", index=False)
    logger.info("Gold (daily station): %d rows", len(daily_station))

    zone_weekly = compute_gold_zone_weekly(silver)
    zone_weekly.to_parquet(GOLD_PATH / "zone_weekly_metrics.parquet", index=False)
    logger.info("Gold (zone weekly): %d rows", len(zone_weekly))

    # Sample insight for interview demo
    logger.info("\n=== TOP ZONES BY AVG AQI (higher = worse air quality) ===")
    top_aqi = (
        daily_station.groupby("zone")["avg_aqi"]
        .mean().round(1).sort_values(ascending=False)
    )
    logger.info("\n%s", top_aqi.to_string())

    exceedances = daily_station["eu_exceedance_days"].sum()
    logger.info("\nTotal EU threshold exceedances: %d station-days", exceedances)


if __name__ == "__main__":
    run()
