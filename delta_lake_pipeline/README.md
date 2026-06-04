# Delta Lake Medallion Pipeline

A local implementation of the Medallion Architecture using **Delta Lake** and
**PySpark** — the same stack used on Databricks at scale. Data flows through
Bronze → Silver → Gold layers, with a dedicated script demonstrating the
Delta-specific features that make it the backbone of the Databricks lakehouse.

## What is Delta Lake?

Delta Lake is an open-source storage format that adds a transaction log
(`_delta_log/`) on top of Parquet files. This gives you:

| Feature | Plain Parquet | Delta Lake |
|---------|:---:|:---:|
| ACID transactions | ✗ | ✓ |
| Schema enforcement | ✗ | ✓ |
| Schema evolution | ✗ | ✓ |
| Time travel | ✗ | ✓ |
| UPSERT / MERGE | ✗ | ✓ |
| File compaction (OPTIMIZE) | ✗ | ✓ |
| Data skipping (ZORDER) | ✗ | ✓ |

---

## Architecture

```
data/yellow_tripdata_2024-01.parquet   (raw NYC TLC source)
              │
              ▼
     ┌─────────────────┐
     │   bronze.py     │  WRITE: delta/bronze/taxi_trips
     │                 │  + metadata cols (_ingest_ts, _source_file)
     │  no transforms  │  + full transaction log
     └────────┬────────┘
              │
              ▼
     ┌─────────────────┐
     │   silver.py     │  READ:  delta/bronze/taxi_trips
     │                 │  WRITE: delta/silver/taxi_trips
     │  quality rules  │  + partitioned by pickup_date
     │  derived cols   │  + trip_duration, pickup_hour
     └────────┬────────┘
              │
              ▼
     ┌─────────────────┐
     │    gold.py      │  READ:  delta/silver/taxi_trips
     │                 │  WRITE: delta/gold/fct_trips_daily
     │  daily aggreg.  │  + OPTIMIZE ZORDER BY pickup_date
     └────────┬────────┘
              │
              ▼
     ┌─────────────────┐
     │ time_travel.py  │  Demonstrates Delta-specific features on gold table
     └─────────────────┘
```

---

## Files

| File | Purpose |
|------|---------|
| `bronze.py` | Ingest raw Parquet → Delta Bronze table |
| `silver.py` | Clean + enrich → Delta Silver table (partitioned) |
| `gold.py` | Aggregate → Delta Gold table (ZORDER applied) |
| `time_travel.py` | Time travel, schema evolution, OPTIMIZE, VACUUM |
| `requirements.txt` | Python dependencies |

---

## Delta Lake Concepts Explained

### Bronze Layer
Raw data copied exactly from the source. Only audit metadata is added
(`_ingest_timestamp`, `_source_file`). The Bronze table is the recovery point —
if Silver or Gold logic has a bug, you replay from Bronze without re-ingesting.

### Silver Layer
Validated, typed, and enriched data. Partitioned by `pickup_date` so downstream
queries with a date filter only scan relevant partitions (partition pruning).
Invalid records are filtered and the reason is documented in code.

### Gold Layer
Pre-aggregated metrics optimised for BI consumption. After writing, `OPTIMIZE`
compacts many small Parquet files into fewer, larger ones. `ZORDER BY pickup_date`
physically co-locates rows for the same date, enabling Delta's **data skipping**
to skip irrelevant files when a date filter is applied.

### Time Travel
Every Delta write appends a JSON commit to `_delta_log/`. You can query any
historical version:
```python
spark.read.format("delta").option("versionAsOf", 0).load(path)
spark.read.format("delta").option("timestampAsOf", "2024-01-15").load(path)
```

### Schema Evolution
Adding a column to an existing Delta table without breaking readers:
```python
df.write.format("delta").mode("overwrite").option("mergeSchema", "true").save(path)
```

---

## Prerequisites

- Python 3.10+
- Java 11+ (required by PySpark)

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Download source data (~50 MB)
mkdir -p data
curl -L -o data/yellow_tripdata_2024-01.parquet \
  https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet

# 3. Run the medallion pipeline in order
python bronze.py
python silver.py
python gold.py

# 4. Explore Delta features
python time_travel.py
```

## On Databricks

Replace local paths with Unity Catalog table names and DBFS/S3 paths:

```python
# Instead of: spark.read.parquet("data/yellow_tripdata_2024-01.parquet")
spark.read.parquet("s3://my-bucket/raw/nyc-taxi/")

# Instead of: df.write.format("delta").save("delta/gold/fct_trips_daily")
df.write.format("delta").saveAsTable("main.gold.fct_trips_daily")
```
