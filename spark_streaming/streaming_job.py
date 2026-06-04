"""
Spark Structured Streaming: Kafka → Delta Lake

This job reads e-commerce order events from a Kafka topic, computes per-category
revenue in tumbling 1-minute windows, and writes results to a Delta Lake sink.

Key Structured Streaming concepts demonstrated:
  - readStream from Kafka (JSON decoding, schema enforcement)
  - Event-time processing with watermarking (handles late-arriving data)
  - Windowed aggregation (tumbling window, stateful)
  - writeStream to Delta with checkpointing (exactly-once delivery)

On Databricks this job would be deployed as:
  - A Delta Live Tables (DLT) pipeline for managed streaming + lineage
  - Or a streaming Databricks Job on a dedicated cluster

The Delta sink guarantees exactly-once delivery via checkpointing:
  - On restart, Spark reads the checkpoint to know which Kafka offsets
    were already committed, then resumes from exactly that point.
"""
import logging
import signal
import sys

import pyspark.sql.functions as F
from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession
from pyspark.sql.types import (
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

# ── Configuration ─────────────────────────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
KAFKA_TOPIC             = "orders"
DELTA_SINK_PATH         = "delta/streaming/revenue_by_category"
CHECKPOINT_PATH         = "delta/checkpoints/revenue_by_category"

# Matches the JSON schema produced by kafka_streaming/producer.py
ORDER_SCHEMA = StructType([
    StructField("order_id",        StringType(),  nullable=True),
    StructField("customer_id",     StringType(),  nullable=True),
    StructField("customer_name",   StringType(),  nullable=True),
    StructField("product_name",    StringType(),  nullable=True),
    StructField("category",        StringType(),  nullable=True),
    StructField("unit_price",      DoubleType(),  nullable=True),
    StructField("quantity",        IntegerType(), nullable=True),
    StructField("total_price",     DoubleType(),  nullable=True),
    StructField("payment_method",  StringType(),  nullable=True),
    StructField("created_at",      StringType(),  nullable=True),
])


def build_spark() -> SparkSession:
    """
    Build a SparkSession with both Delta Lake support and the Kafka connector.

    The kafka jar is downloaded automatically via spark.jars.packages.
    On Databricks, both are pre-installed on the cluster — no config needed.
    """
    builder = (
        SparkSession.builder
        .appName("orders_revenue_streaming")
        .config("spark.sql.extensions",
                "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog",
                "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        # Kafka + Delta jars — fetched from Maven on first run
        .config(
            "spark.jars.packages",
            "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,"
            "io.delta:delta-spark_2.12:3.0.0",
        )
        .config("spark.driver.memory", "2g")
        .config("spark.ui.showConsoleProgress", "false")
    )
    return configure_spark_with_delta_pip(builder).getOrCreate()


def build_pipeline(spark: SparkSession):
    """
    Construct the streaming DataFrame pipeline.
    This is lazy — nothing runs until writeStream.start() is called.
    """
    # ── 1. Read raw bytes from Kafka ─────────────────────────────────────────
    # Each Kafka record has: key, value (bytes), topic, partition, offset, timestamp
    raw_stream = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", KAFKA_TOPIC)
        # "latest" = start reading new messages only (skip historical backlog)
        # Use "earliest" to replay all messages from the beginning
        .option("startingOffsets", "latest")
        # Don't fail if Kafka topic is temporarily unavailable
        .option("failOnDataLoss", "false")
        # Limit Kafka fetch per micro-batch to keep latency low
        .option("maxOffsetsPerTrigger", 10_000)
        .load()
    )

    # ── 2. Decode JSON payload ────────────────────────────────────────────────
    # Kafka value is raw bytes → cast to string → parse as JSON → flatten struct
    parsed = (
        raw_stream
        .select(
            # event_time comes from Kafka's server-side timestamp
            F.col("timestamp").alias("event_time"),
            F.from_json(F.col("value").cast("string"), ORDER_SCHEMA).alias("data"),
        )
        .select("event_time", "data.*")
        # Parse created_at string into a proper timestamp for event-time processing
        .withColumn("created_at", F.to_timestamp("created_at"))
    )

    # ── 3. Watermark + windowed aggregation ───────────────────────────────────
    # withWatermark("created_at", "10 minutes"):
    #   Tells Spark to wait up to 10 minutes for late-arriving events.
    #   Once the watermark advances past a window, that window's state is
    #   finalised and the result row is emitted. This bounds memory usage.
    #
    # window("created_at", "1 minute"):
    #   Tumbling window — non-overlapping 1-minute buckets.
    #   Use slideDuration for sliding windows: window(col, "5 min", "1 min")
    revenue_by_category = (
        parsed
        .withWatermark("created_at", "10 minutes")
        .groupBy(
            F.window("created_at", "1 minute").alias("window"),
            F.col("category"),
        )
        .agg(
            F.count("order_id")                    .alias("order_count"),
            F.round(F.sum("total_price"),    2)    .alias("revenue"),
            F.round(F.avg("total_price"),    2)    .alias("avg_order_value"),
            F.round(F.sum("unit_price"),     2)    .alias("gross_product_value"),
        )
        .select(
            F.col("window.start").alias("window_start"),
            F.col("window.end")  .alias("window_end"),
            "category", "order_count", "revenue", "avg_order_value", "gross_product_value",
        )
    )

    return revenue_by_category


def run(spark: SparkSession) -> None:
    logger.info("Starting Structured Streaming job")
    logger.info("  Kafka:  %s (topic: %s)", KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC)
    logger.info("  Sink:   %s", DELTA_SINK_PATH)
    logger.info("  Checkpoint: %s", CHECKPOINT_PATH)

    pipeline = build_pipeline(spark)

    # ── 4. Write stream to Delta ──────────────────────────────────────────────
    # outputMode("append"):
    #   Only emit a row once its window is finalised (after the watermark passes).
    #   Use "complete" to update all windows every micro-batch (more expensive).
    #
    # checkpointLocation:
    #   Stores Kafka offsets + aggregation state to HDFS/S3/DBFS.
    #   On restart, Spark reads the checkpoint and resumes exactly where it left off.
    #   This is what gives exactly-once delivery guarantees.
    query = (
        pipeline.writeStream
        .format("delta")
        .outputMode("append")
        .option("checkpointLocation", CHECKPOINT_PATH)
        .option("mergeSchema", "true")
        .trigger(processingTime="10 seconds")   # micro-batch interval
        .start(DELTA_SINK_PATH)
    )

    logger.info("Streaming query started (query id: %s). Press Ctrl+C to stop.", query.id)

    # Graceful shutdown on SIGINT / SIGTERM
    def _stop(signum, frame):
        logger.info("Received signal %s — stopping query...", signum)
        query.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT,  _stop)
    signal.signal(signal.SIGTERM, _stop)

    query.awaitTermination()


if __name__ == "__main__":
    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")
    try:
        run(spark)
    finally:
        spark.stop()
