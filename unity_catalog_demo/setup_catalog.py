"""
Unity Catalog Demo — Catalog and Table Setup

Unity Catalog is Databricks' unified data governance layer. It introduces a
three-level namespace that every table in a Databricks workspace lives under:

    catalog  →  schema (database)  →  table
    ───────────────────────────────────────
    portfolio   bronze              raw_weather
    portfolio   silver              clean_weather
    portfolio   gold                weather_daily
    portfolio   analytics           weather_report

On real Databricks you create these with SQL:
    CREATE CATALOG IF NOT EXISTS portfolio;
    USE CATALOG portfolio;
    CREATE SCHEMA IF NOT EXISTS bronze;
    CREATE TABLE bronze.raw_weather (...) USING DELTA;

This script simulates the same namespace locally using PySpark + Delta Lake.
Each "schema" maps to a subdirectory under delta/portfolio/.

Key Unity Catalog benefits demonstrated:
  - Centralised access control (one place to manage permissions)
  - Cross-workspace data sharing (Delta Sharing protocol)
  - Automatic data lineage capture
  - Column-level tagging for PII / sensitivity classification
"""
import logging
from pathlib import Path

import pyspark.sql.functions as F
from delta import DeltaTable, configure_spark_with_delta_pip
from pyspark.sql import SparkSession
from pyspark.sql.types import (
    DateType,
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Three-level namespace (simulated locally as directory paths) ───────────────
CATALOG = "portfolio"

# catalog.schema → local path
SCHEMA_PATHS: dict[str, str] = {
    "bronze":    f"delta/{CATALOG}/bronze",
    "silver":    f"delta/{CATALOG}/silver",
    "gold":      f"delta/{CATALOG}/gold",
    "analytics": f"delta/{CATALOG}/analytics",
}

# Fully-qualified table names → local Delta paths
TABLE_PATHS: dict[str, str] = {
    f"{CATALOG}.bronze.raw_weather":        f"delta/{CATALOG}/bronze/raw_weather",
    f"{CATALOG}.silver.clean_weather":      f"delta/{CATALOG}/silver/clean_weather",
    f"{CATALOG}.gold.weather_daily":        f"delta/{CATALOG}/gold/weather_daily",
    f"{CATALOG}.analytics.weather_report":  f"delta/{CATALOG}/analytics/weather_report",
}

WEATHER_SCHEMA = StructType([
    StructField("date",             StringType(),  nullable=False),
    StructField("city",             StringType(),  nullable=False),
    StructField("temperature_max",  DoubleType(),  nullable=True),
    StructField("temperature_min",  DoubleType(),  nullable=True),
    StructField("precipitation_mm", DoubleType(),  nullable=True),
    StructField("wind_speed_kmh",   DoubleType(),  nullable=True),
    StructField("weather_code",     IntegerType(), nullable=True),
])

SAMPLE_RECORDS = [
    ("2024-01-01", "New York",  8.5, -2.3,  0.0, 15.2, 1),
    ("2024-01-01", "London",    6.1,  1.2,  5.3, 20.1, 61),
    ("2024-01-01", "Tokyo",    10.3,  3.1,  2.1, 12.5, 2),
    ("2024-01-01", "Sydney",   22.4, 14.1,  0.0,  8.3, 0),
    ("2024-01-02", "New York", 10.1, -1.2,  2.5, 18.3, 3),
    ("2024-01-02", "London",    7.2,  2.1, 10.1, 22.4, 63),
    ("2024-01-02", "Tokyo",    11.5,  4.2,  0.0, 10.2, 0),
    ("2024-01-02", "Sydney",   24.1, 15.8,  1.2,  9.1, 1),
]


def build_spark() -> SparkSession:
    builder = (
        SparkSession.builder
        .appName("unity_catalog_setup")
        .config("spark.sql.extensions",
                "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog",
                "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.driver.memory", "2g")
        .config("spark.ui.showConsoleProgress", "false")
    )
    return configure_spark_with_delta_pip(builder).getOrCreate()


def create_catalog_structure() -> None:
    """Create directory tree that mirrors the Unity Catalog three-level namespace."""
    logger.info("Creating catalog structure for: %s", CATALOG)
    for schema, path in SCHEMA_PATHS.items():
        Path(path).mkdir(parents=True, exist_ok=True)
        logger.info("  %s.%s  →  %s/", CATALOG, schema, path)


def populate_bronze(spark: SparkSession) -> None:
    """Bronze: raw data, no changes."""
    fqn  = f"{CATALOG}.bronze.raw_weather"
    path = TABLE_PATHS[fqn]
    df   = spark.createDataFrame(SAMPLE_RECORDS, schema=WEATHER_SCHEMA)
    df   = df.withColumn("date", F.to_date("date")) \
             .withColumn("_ingest_ts", F.current_timestamp())

    df.write.format("delta").mode("overwrite").save(path)
    logger.info("Created %-45s  (%d rows)", fqn, df.count())


def populate_silver(spark: SparkSession) -> None:
    """Silver: validated, with data quality filters applied."""
    bronze_df = spark.read.format("delta").load(TABLE_PATHS[f"{CATALOG}.bronze.raw_weather"])

    silver_df = (
        bronze_df
        .filter(F.col("temperature_max") > F.col("temperature_min"))
        .filter(F.col("precipitation_mm") >= 0)
        .withColumn("temp_range", F.col("temperature_max") - F.col("temperature_min"))
        .drop("_ingest_ts")
        .withColumn("_silver_ts", F.current_timestamp())
    )

    fqn  = f"{CATALOG}.silver.clean_weather"
    path = TABLE_PATHS[fqn]
    silver_df.write.format("delta").mode("overwrite").save(path)
    logger.info("Created %-45s  (%d rows)", fqn, silver_df.count())


def populate_gold(spark: SparkSession) -> None:
    """Gold: daily aggregates per city, analytics-ready."""
    silver_df = spark.read.format("delta").load(TABLE_PATHS[f"{CATALOG}.silver.clean_weather"])

    gold_df = (
        silver_df
        .groupBy("date")
        .agg(
            F.count("city")                          .alias("city_count"),
            F.round(F.avg("temperature_max"),   2)   .alias("global_avg_max_temp"),
            F.round(F.avg("temperature_min"),   2)   .alias("global_avg_min_temp"),
            F.round(F.sum("precipitation_mm"),  2)   .alias("total_precipitation"),
            F.round(F.avg("wind_speed_kmh"),    2)   .alias("avg_wind_speed"),
        )
        .orderBy("date")
    )

    fqn  = f"{CATALOG}.gold.weather_daily"
    path = TABLE_PATHS[fqn]
    gold_df.write.format("delta").mode("overwrite").save(path)
    logger.info("Created %-45s  (%d rows)", fqn, gold_df.count())


def show_catalog_summary(spark: SparkSession) -> None:
    """Print a summary of all tables — mirrors `SHOW TABLES IN catalog` on Databricks."""
    logger.info("=" * 60)
    logger.info("  CATALOG: %s", CATALOG.upper())
    logger.info("  (equivalent to: SHOW TABLES IN %s.*)", CATALOG)
    logger.info("=" * 60)
    for fqn, path in TABLE_PATHS.items():
        try:
            df  = spark.read.format("delta").load(path)
            dt  = DeltaTable.forPath(spark, path)
            ver = dt.history(1).select("version").collect()[0][0]
            logger.info(
                "  %-48s  rows=%d  version=%d  cols=%d",
                fqn, df.count(), ver, len(df.columns),
            )
        except Exception:
            logger.warning("  %-48s  (not yet created)", fqn)


if __name__ == "__main__":
    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")
    try:
        create_catalog_structure()
        populate_bronze(spark)
        populate_silver(spark)
        populate_gold(spark)
        show_catalog_summary(spark)
    finally:
        spark.stop()
