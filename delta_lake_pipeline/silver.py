"""
Silver Layer — Validated and Enriched Delta Table

The Silver layer sits between raw Bronze and analytics-ready Gold.
Rules:
  - All columns have correct types
  - Invalid/impossible records are filtered out (not silently dropped)
  - New derived columns are added (trip_duration, pickup_date, pickup_hour)
  - Data is partitioned for efficient downstream queries

On Databricks the Silver write would target a Unity Catalog table:
    df.write.format("delta").saveAsTable("catalog.silver.taxi_trips")

The MERGE (upsert) pattern shown below is used in incremental pipelines
to avoid full rewrites when only new data arrives.
"""
import logging
import sys

import pyspark.sql.functions as F
from delta import DeltaTable, configure_spark_with_delta_pip
from pyspark.sql import DataFrame, SparkSession

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

BRONZE_PATH = "delta/bronze/taxi_trips"
SILVER_PATH = "delta/silver/taxi_trips"


def build_spark() -> SparkSession:
    builder = (
        SparkSession.builder
        .appName("silver_transform")
        .config("spark.sql.extensions",
                "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog",
                "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.driver.memory", "2g")
        .config("spark.ui.showConsoleProgress", "false")
    )
    return configure_spark_with_delta_pip(builder).getOrCreate()


def apply_quality_filters(df: DataFrame) -> DataFrame:
    """
    Drop records that violate physical constraints.
    Each filter is documented so data analysts know exactly what was removed.
    """
    # Rule 1: required columns must be non-null
    df = df.filter(
        F.col("tpep_pickup_datetime").isNotNull()
        & F.col("tpep_dropoff_datetime").isNotNull()
        & F.col("passenger_count").isNotNull()
    )

    # Rule 2: trip must have moved and cost money
    df = df.filter(
        (F.col("trip_distance")   > 0)
        & (F.col("fare_amount")   > 0)
        & (F.col("total_amount")  > 0)
        & (F.col("passenger_count") > 0)
    )

    # Rule 3: keep only records from 2024 (source file has stray 2002/2009 rows)
    df = df.filter(F.year("tpep_pickup_datetime") == 2024)

    # Rule 4: dropoff must follow pickup
    df = df.filter(
        F.col("tpep_dropoff_datetime") > F.col("tpep_pickup_datetime")
    )

    return df


def add_derived_columns(df: DataFrame) -> DataFrame:
    """Add business-useful columns derived from the raw data."""
    return (
        df
        # Convenience date/time columns for partitioning and aggregation
        .withColumn("pickup_date",  F.to_date("tpep_pickup_datetime"))
        .withColumn("pickup_hour",  F.hour("tpep_pickup_datetime"))
        # Trip duration: useful for speed and quality metrics
        .withColumn(
            "trip_duration_minutes",
            F.round(
                (
                    F.unix_timestamp("tpep_dropoff_datetime")
                    - F.unix_timestamp("tpep_pickup_datetime")
                ) / 60.0,
                2,
            ),
        )
        # Rule 5 (applied after derivation): filter absurd durations
        .filter(
            (F.col("trip_duration_minutes") >= 1)
            & (F.col("trip_duration_minutes") <= 360)
        )
        # Silver audit column
        .withColumn("_silver_timestamp", F.current_timestamp())
    )


def transform_silver(spark: SparkSession) -> None:
    if not DeltaTable.isDeltaTable(spark, BRONZE_PATH):
        logger.error("Bronze Delta table not found at %s — run bronze.py first", BRONZE_PATH)
        sys.exit(1)

    logger.info("Reading Bronze Delta table: %s", BRONZE_PATH)
    bronze_df = spark.read.format("delta").load(BRONZE_PATH)
    before = bronze_df.count()
    logger.info("Bronze rows: %d", before)

    filtered_df   = apply_quality_filters(bronze_df)
    silver_df     = add_derived_columns(filtered_df)
    after         = silver_df.count()
    logger.info("Silver rows: %d  (removed %d = %.1f%%)", after, before - after, (before - after) / before * 100)

    # ── Write partitioned Silver table ────────────────────────────────────────
    # partitionBy("pickup_date") means Spark writes one sub-directory per day.
    # Downstream queries with a date filter skip irrelevant partitions entirely
    # (partition pruning), making aggregations 10-100x faster on large datasets.
    logger.info("Writing Silver Delta table: %s (partitioned by pickup_date)", SILVER_PATH)
    (
        silver_df.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .partitionBy("pickup_date")
        .save(SILVER_PATH)
    )

    dt = DeltaTable.forPath(spark, SILVER_PATH)
    logger.info("Silver table history:")
    dt.history(3).select("version", "timestamp", "operation").show(truncate=False)
    logger.info("Silver schema:")
    spark.read.format("delta").load(SILVER_PATH).printSchema()
    logger.info("Silver complete.")


if __name__ == "__main__":
    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")
    try:
        transform_silver(spark)
    finally:
        spark.stop()
