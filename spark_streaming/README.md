# Spark Structured Streaming — Kafka → Delta Lake

A **Spark Structured Streaming** pipeline that reads e-commerce order events
from Apache Kafka, computes per-category revenue in tumbling 1-minute windows,
and writes results to a **Delta Lake** sink with exactly-once delivery.

This is the streaming equivalent of Project 3 (`kafka_streaming/`), upgraded
from a pure Python consumer to a production-grade Spark job with persistent
state, watermarking, and a queryable Delta output table.

---

## Architecture

```
┌─────────────────────┐     JSON events     ┌────────────────────────┐
│   kafka_streaming/  │ ──────────────────▶ │   Apache Kafka         │
│   producer.py       │   ~1 msg/sec        │   topic: "orders"      │
│                     │                     │   localhost:9092        │
└─────────────────────┘                     └───────────┬────────────┘
                                                        │
                                          Kafka source connector
                                                        │
                                                        ▼
                                     ┌──────────────────────────────────┐
                                     │     streaming_job.py             │
                                     │                                  │
                                     │  1. Decode JSON payload          │
                                     │  2. Watermark (10 min)          │
                                     │  3. Tumbling window (1 min)     │
                                     │  4. GROUP BY category            │
                                     │     → order_count, revenue,     │
                                     │       avg_order_value           │
                                     └───────────────┬──────────────────┘
                                                     │ exactly-once
                                                     │ (checkpoint)
                                                     ▼
                                     ┌──────────────────────────────────┐
                                     │   Delta Lake Sink                │
                                     │   delta/streaming/               │
                                     │   revenue_by_category            │
                                     │                                  │
                                     │   Queryable via Spark SQL        │
                                     └──────────────────────────────────┘
```

---

## Key Concepts

### Watermarking
```python
.withWatermark("created_at", "10 minutes")
```
Tells Spark how long to wait for late-arriving events before closing a time
window and emitting the result. Without a watermark, Spark must keep all
historical state in memory forever — not viable in long-running jobs.

### Windowed Aggregation
```python
F.window("created_at", "1 minute")
```
Groups events into non-overlapping (tumbling) 1-minute buckets. Revenue and
order counts are accumulated within each window, then emitted once the
watermark passes the window boundary.

### Exactly-Once Delivery
```python
.option("checkpointLocation", CHECKPOINT_PATH)
```
The checkpoint directory stores Kafka offsets and aggregation state.
On restart, Spark reads the checkpoint and resumes from exactly where it left
off — no duplicate rows, no missed events.

### Delta Sink
Writing to Delta instead of plain Parquet gives the output table:
- ACID writes (no partial results visible to readers mid-write)
- Time travel (query previous micro-batch results)
- Schema evolution (add output columns without pipeline downtime)

---

## Files

| File | Purpose |
|------|---------|
| `streaming_job.py` | PySpark Structured Streaming pipeline |
| `start_kafka.sh` | Start a local Kafka broker via Docker |
| `requirements.txt` | Python dependencies |

---

## Prerequisites

- Python 3.10+, Java 11+
- Docker (for Kafka)

## Quick Start

### 1. Start Kafka

```bash
chmod +x start_kafka.sh
./start_kafka.sh
```

### 2. Start the order producer

In a separate terminal, use the producer from `kafka_streaming/`:

```bash
cd ../kafka_streaming
pip install -r requirements.txt
python producer.py
```

### 3. Run the Spark streaming job

```bash
pip install -r requirements.txt
python streaming_job.py
```

Spark downloads the Kafka connector jar on first run (~30 s). Once running,
the Delta table at `delta/streaming/revenue_by_category` is updated every
10 seconds.

### 4. Query the output (in another terminal)

```python
from pyspark.sql import SparkSession
from delta import configure_spark_with_delta_pip

spark = configure_spark_with_delta_pip(
    SparkSession.builder
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
    .config("spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog")
).getOrCreate()

spark.read.format("delta").load("delta/streaming/revenue_by_category") \
    .orderBy("window_start", "category").show()
```

### 5. Tear down

```bash
docker stop kafka-for-spark && docker rm kafka-for-spark
```

## On Databricks

Deploy as a Delta Live Tables pipeline:

```python
import dlt

@dlt.table(comment="Per-category revenue in 1-minute tumbling windows")
def revenue_by_category():
    return (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", spark.conf.get("kafka.bootstrap"))
        .option("subscribe", "orders")
        .load()
        # ... same transformation logic ...
    )
```

DLT handles checkpointing, retries, and schema inference automatically.
