"""
Gold Layer — Analytics-Ready Daily Metrics

The Gold layer contains pre-aggregated, business-friendly tables that are
optimised for BI tools, dashboards, and ML feature stores.

Design principles applied here:
  - One row per business grain (pickup_date)
  - All columns named for business users, not engineers
  - ZORDER applied on the write to co-locate related data in the same files,
    enabling data skipping for date-range queries (critical at petabyte scale)

On Databricks, Gold tables are typically:
  - Registered in Unity Catalog and exposed to BI tools via SQL Warehouse
  - Queried directly from Power BI / Tableau via the Databricks connector
  - Refreshed on a schedule via Databricks Workflows or Delta Live Tables
"""
import logging
import sys

import pyspark.sql.functions as F
from delta import DeltaTable, configure_spark_with_delta_pip
from pyspark.sql import SparkSession

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

SILVER_PATH = "delta/silver/taxi_trips"
GOLD_PATH   = "delta/gold/fct_trips_daily"


def build_spark() -> SparkSession:
    builder = (
        SparkSession.builder
        .appName("gold_aggregate")
        .config("spark.sql.extensions",
                "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog",
                "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.driver.memory", "2g")
        .config("spark.ui.showConsoleProgress", "false")
    )
    return configure_spark_with_delta_pip(builder).getOrCreate()


def build_gold(spark: SparkSession) -> None:
    if not DeltaTable.isDeltaTable(spark, SILVER_PATH):
        logger.error("Silver Delta table not found at %s — run silver.py first", SILVER_PATH)
        sys.exit(1)

    logger.info("Reading Silver Delta table: %s", SILVER_PATH)
    silver_df = spark.read.format("delta").load(SILVER_PATH)

    gold_df = (
        silver_df
        .groupBy("pickup_date")
        .agg(
            # ── Volume ────────────────────────────────────────────────────────
            F.count("*")                          .alias("total_trips"),
            F.sum("passenger_count")              .alias("total_passengers"),

            # ── Revenue ───────────────────────────────────────────────────────
            F.round(F.sum("total_amount"),   2)   .alias("total_revenue"),
            F.round(F.avg("fare_amount"),    2)   .alias("avg_fare"),
            F.round(F.sum("tip_amount"),     2)   .alias("total_tips"),
            F.round(
                F.avg(F.col("tip_amount") / F.when(F.col("fare_amount") > 0, F.col("fare_amount"))), 4
            )                                     .alias("avg_tip_rate"),

            # ── Efficiency ────────────────────────────────────────────────────
            F.round(F.avg("trip_distance"),            2) .alias("avg_distance_miles"),
            F.round(F.avg("trip_duration_minutes"),    2) .alias("avg_duration_minutes"),
            F.round(
                F.avg(
                    F.col("trip_distance")
                    / F.when(F.col("trip_duration_minutes") > 0,
                              F.col("trip_duration_minutes") / 60.0)
                ), 2
            )                                            .alias("avg_speed_mph"),

            # ── Rush-hour breakdown ───────────────────────────────────────────
            F.sum(F.when(F.col("pickup_hour").between(7,  9),  1).otherwise(0))
                                                         .alias("morning_rush_trips"),
            F.sum(F.when(F.col("pickup_hour").between(17, 19), 1).otherwise(0))
                                                         .alias("evening_rush_trips"),
        )
        .orderBy("pickup_date")
    )

    row_count = gold_df.count()
    logger.info("Gold table: %d daily rows", row_count)

    # ── Write Gold Delta table ─────────────────────────────────────────────────
    logger.info("Writing Gold Delta table: %s", GOLD_PATH)
    (
        gold_df.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .save(GOLD_PATH)
    )

    # ── OPTIMIZE + ZORDER ─────────────────────────────────────────────────────
    # OPTIMIZE compacts many small files into larger ones (reduces S3 LIST calls).
    # ZORDER BY pickup_date co-locates rows for the same date in the same files,
    # so a query like WHERE pickup_date = '2024-01-15' reads far less data.
    logger.info("Running OPTIMIZE ZORDER BY pickup_date...")
    spark.sql(f"OPTIMIZE delta.`{GOLD_PATH}` ZORDER BY (pickup_date)")

    logger.info("Top 10 days by total revenue:")
    spark.read.format("delta").load(GOLD_PATH) \
        .orderBy(F.desc("total_revenue")) \
        .select("pickup_date", "total_trips", "total_revenue", "avg_fare") \
        .show(10)

    DeltaTable.forPath(spark, GOLD_PATH) \
        .history(3) \
        .select("version", "timestamp", "operation") \
        .show(truncate=False)

    logger.info("Gold complete.")


if __name__ == "__main__":
    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")
    try:
        build_gold(spark)
    finally:
        spark.stop()
