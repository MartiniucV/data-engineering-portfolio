"""
Delta Lake Time Travel, Schema Evolution, and Maintenance Demo

Delta Lake's transaction log (_delta_log/) records every write as a JSON
commit entry. This makes three powerful features possible:

1. TIME TRAVEL — query any historical version of a table
   SELECT * FROM delta.`path/to/table` VERSION AS OF 3
   SELECT * FROM delta.`path/to/table` TIMESTAMP AS OF '2024-01-15'

2. SCHEMA EVOLUTION — add columns without breaking existing readers
   df.write.option("mergeSchema", "true").format("delta").mode("append").save(path)

3. OPTIMIZE + ZORDER — file compaction and data skipping index

4. VACUUM — remove files no longer referenced by any version within
   the retention window (default 7 days)

These four features together are why Delta Lake is preferred over plain
Parquet on Databricks — Parquet has none of them.
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

GOLD_PATH = "delta/gold/fct_trips_daily"

DIVIDER = "=" * 60


def build_spark() -> SparkSession:
    builder = (
        SparkSession.builder
        .appName("time_travel_demo")
        .config("spark.sql.extensions",
                "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog",
                "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        # Allow schema evolution on writes
        .config("spark.databricks.delta.schema.autoMerge.enabled", "true")
        # Allow VACUUM with short retention (demo only — never do this in production)
        .config("spark.databricks.delta.retentionDurationCheck.enabled", "false")
        .config("spark.driver.memory", "2g")
        .config("spark.ui.showConsoleProgress", "false")
    )
    return configure_spark_with_delta_pip(builder).getOrCreate()


def show_divider(title: str) -> None:
    logger.info("%s", DIVIDER)
    logger.info("  %s", title)
    logger.info("%s", DIVIDER)


def demo_audit_log(spark: SparkSession) -> None:
    show_divider("1. DELTA AUDIT LOG")
    dt = DeltaTable.forPath(spark, GOLD_PATH)
    (
        dt.history()
        .select("version", "timestamp", "operation", "operationMetrics")
        .show(truncate=False)
    )
    # On Databricks you'd also use:
    # DESCRIBE HISTORY delta.`path`
    # or query system.access.audit for cluster-wide audit logs


def demo_time_travel_by_version(spark: SparkSession) -> None:
    show_divider("2. TIME TRAVEL — query version 0")
    # Read the table as it was immediately after the first write
    v0 = spark.read.format("delta").option("versionAsOf", 0).load(GOLD_PATH)
    logger.info("Version 0: %d rows, columns: %s", v0.count(), v0.columns)
    v0.orderBy("pickup_date").show(5)

    # You can also use SQL syntax on Databricks:
    # spark.sql("SELECT * FROM delta.`path` VERSION AS OF 0")


def demo_schema_evolution(spark: SparkSession) -> None:
    show_divider("3. SCHEMA EVOLUTION — add revenue_per_trip")
    current_df = spark.read.format("delta").load(GOLD_PATH)
    logger.info("Columns before evolution: %s", current_df.columns)

    # Add a derived column and re-write with mergeSchema=true
    # Delta will ADD the new column to the schema without touching existing data
    evolved_df = current_df.withColumn(
        "revenue_per_trip",
        F.round(F.col("total_revenue") / F.col("total_trips"), 2),
    ).withColumn(
        "tips_pct_of_revenue",
        F.round(F.col("total_tips") / F.col("total_revenue") * 100, 2),
    )

    (
        evolved_df.write
        .format("delta")
        .mode("overwrite")
        # mergeSchema=true: add new columns; fail on incompatible type changes
        .option("mergeSchema", "true")
        .save(GOLD_PATH)
    )

    logger.info("Columns after evolution: %s",
                spark.read.format("delta").load(GOLD_PATH).columns)

    # Old version is still readable — it just lacks the new columns
    v0 = spark.read.format("delta").option("versionAsOf", 0).load(GOLD_PATH)
    logger.info("Version 0 columns (no new columns): %s", v0.columns)


def demo_restore(spark: SparkSession) -> None:
    show_divider("4. RESTORE — roll back to version 0")
    # RESTORE undoes recent writes without touching the transaction log history.
    # Use case: bad data written to production; roll back while you investigate.
    dt = DeltaTable.forPath(spark, GOLD_PATH)
    # Restore via SQL (works the same on Databricks)
    spark.sql(f"RESTORE TABLE delta.`{GOLD_PATH}` TO VERSION AS OF 0")
    logger.info("Restored to version 0: %d rows",
                spark.read.format("delta").load(GOLD_PATH).count())


def demo_optimize(spark: SparkSession) -> None:
    show_divider("5. OPTIMIZE — compact small files")
    # After many small writes (e.g., streaming micro-batches), Delta tables
    # accumulate many tiny Parquet files. OPTIMIZE merges them into ~1 GB files.
    # On Databricks, Auto Optimize does this automatically.
    result = spark.sql(f"OPTIMIZE delta.`{GOLD_PATH}`")
    result.show(truncate=False)


def demo_vacuum(spark: SparkSession) -> None:
    show_divider("6. VACUUM — dry run (shows files to be deleted)")
    # VACUUM deletes Parquet files that are no longer referenced by any version
    # within the retention window. After VACUUM you can no longer time-travel
    # to versions older than the retention period.
    # DRY RUN shows what would be deleted without actually deleting anything.
    spark.sql(f"VACUUM delta.`{GOLD_PATH}` RETAIN 168 HOURS DRY RUN").show(truncate=False)
    logger.info("(DRY RUN only — no files were deleted)")


def run(spark: SparkSession) -> None:
    if not DeltaTable.isDeltaTable(spark, GOLD_PATH):
        logger.error("Gold Delta table not found at %s — run gold.py first", GOLD_PATH)
        sys.exit(1)

    demo_audit_log(spark)
    demo_time_travel_by_version(spark)
    demo_schema_evolution(spark)
    demo_restore(spark)
    demo_optimize(spark)
    demo_vacuum(spark)
    logger.info("Time travel demo complete.")


if __name__ == "__main__":
    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")
    try:
        run(spark)
    finally:
        spark.stop()
