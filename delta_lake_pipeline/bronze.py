"""
Bronze Layer — Raw Ingestion into Delta Lake

The Bronze layer is the landing zone for raw data. The rule is simple:
copy the source data exactly as-is and add audit metadata columns.
No business logic, no transformations — just preserve the original bytes
so you can always replay the pipeline from scratch.

On Databricks this would read from:
  - DBFS:          spark.read.parquet("dbfs:/mnt/raw/nyc_taxi/")
  - Unity Catalog: spark.read.table("catalog.raw.taxi_trips")
  - Cloud storage: spark.read.parquet("s3://bucket/nyc-taxi/")

Locally we read from a relative path and write a local Delta table.
"""
import logging
import sys
from pathlib import Path

import pyspark.sql.functions as F
from delta import DeltaTable, configure_spark_with_delta_pip
from pyspark.sql import SparkSession

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
# Download source data:
#   curl -L -o data/yellow_tripdata_2024-01.parquet \
#     https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet
RAW_PARQUET  = "data/yellow_tripdata_2024-01.parquet"
BRONZE_PATH  = "delta/bronze/taxi_trips"


def build_spark() -> SparkSession:
    """
    Configure a local SparkSession with Delta Lake support.

    On Databricks the session is pre-configured — you call SparkSession.getOrCreate()
    and Delta is already enabled cluster-wide.
    """
    builder = (
        SparkSession.builder
        .appName("bronze_ingest")
        # These two settings enable the Delta Lake SQL extensions
        .config("spark.sql.extensions",
                "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog",
                "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.driver.memory", "2g")
        # Suppress verbose Spark log output in the console
        .config("spark.ui.showConsoleProgress", "false")
    )
    # configure_spark_with_delta_pip downloads the correct Delta jars automatically
    return configure_spark_with_delta_pip(builder).getOrCreate()


def ingest_bronze(spark: SparkSession) -> None:
    raw_path = Path(RAW_PARQUET)
    if not raw_path.exists():
        logger.error("Raw Parquet not found: %s", raw_path)
        logger.error("Download it with:")
        logger.error(
            "  curl -L -o %s "
            "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet",
            raw_path,
        )
        sys.exit(1)

    logger.info("Reading raw Parquet: %s", raw_path)
    df = spark.read.parquet(str(raw_path))

    original_count = df.count()
    logger.info("Source rows: %d", original_count)

    # ── Bronze rule: add metadata, never change source columns ────────────────
    df = (
        df
        .withColumn("_ingest_timestamp", F.current_timestamp())
        .withColumn("_source_file",       F.lit(str(raw_path)))
        .withColumn("_batch_id",           F.lit(1))
    )

    # ── Write to Delta (overwrite = idempotent re-runs) ───────────────────────
    logger.info("Writing Bronze Delta table to %s", BRONZE_PATH)
    (
        df.write
        .format("delta")
        .mode("overwrite")
        # overwriteSchema allows re-running after upstream schema changes
        .option("overwriteSchema", "true")
        .save(BRONZE_PATH)
    )

    # ── Verify and show Delta audit log ───────────────────────────────────────
    dt = DeltaTable.forPath(spark, BRONZE_PATH)
    logger.info("Delta table history:")
    (
        dt.history(5)
        .select("version", "timestamp", "operation", "operationMetrics")
        .show(truncate=False)
    )

    written = spark.read.format("delta").load(BRONZE_PATH).count()
    logger.info("Bronze complete: %d rows written to %s", written, BRONZE_PATH)


if __name__ == "__main__":
    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")
    try:
        ingest_bronze(spark)
    finally:
        spark.stop()
