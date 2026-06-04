# 📊 Data Engineering Portfolio

**Vlad Martiniuc** · [GitHub](https://github.com/MartiniucV) · [martiniuc.vladut@gmail.com](mailto:martiniuc.vladut@gmail.com)

Eight end-to-end data engineering projects spanning the full modern data stack:
batch ELT, medallion architectures, real-time streaming, Delta Lake, Spark
Structured Streaming, dbt on Databricks, and Unity Catalog governance.

---

## 🗂️ Projects at a Glance

| # | Project | Description | Tech Stack | Folder |
|---|---------|-------------|------------|--------|
| 1 | 🚕 **NYC Taxi ELT** | Ingests 3M+ taxi trips into PostgreSQL, models with dbt | PostgreSQL · dbt Core · pandas | [`nyc_taxi_pipeline/`](./nyc_taxi_pipeline) |
| 2 | 🥇 **Medallion Pipeline** | Bronze → Silver → Gold orchestrated by Airflow | Airflow 2.8 · PostgreSQL · Docker | [`medallion_pipeline/`](./medallion_pipeline) |
| 3 | ⚡ **Kafka Streaming** | Real-time e-commerce order stream with live analytics | Kafka · kafka-python · Docker | [`kafka_streaming/`](./kafka_streaming) |
| 4 | 🌐 **Full Data Platform** | API ingest → Parquet → PostgreSQL → quality → dashboard | pandas · SQLAlchemy · Streamlit | [`capstone/`](./capstone) |
| 5 | 🔺 **Delta Lake Pipeline** | Medallion Architecture using Delta Lake locally | PySpark · Delta Lake · pandas | [`delta_lake_pipeline/`](./delta_lake_pipeline) |
| 6 | 🌊 **Spark Streaming** | Structured Streaming from Kafka into Delta Lake sink | PySpark · Delta Lake · Kafka | [`spark_streaming/`](./spark_streaming) |
| 7 | 🔷 **dbt on Databricks** | Same NYC Taxi pipeline targeting Databricks SQL Warehouse | dbt-databricks · Delta Lake · UC | [`dbt_databricks/`](./dbt_databricks) |
| 8 | 🛡️ **Unity Catalog Demo** | Data governance: RLS, column masking, lineage | PySpark · Delta Lake · pandas | [`unity_catalog_demo/`](./unity_catalog_demo) |

---

## 🏛️ Architecture Overview

```
                        DATA ENGINEERING PORTFOLIO
    ┌─────────────────────────────────────────────────────────────────────┐
    │                                                                     │
    │  BATCH PIPELINES                    STREAMING                       │
    │  ┌───────────────────┐              ┌───────────────────────┐       │
    │  │  Projects 1 & 2   │              │  Projects 3 & 6       │       │
    │  │  PostgreSQL + dbt │              │  Kafka → PySpark      │       │
    │  │  Airflow DAGs     │              │  Structured Streaming │       │
    │  │  Medallion Arch.  │              │  Delta Sink           │       │
    │  └───────────────────┘              └───────────────────────┘       │
    │                                                                     │
    │  DELTA LAKE / DATABRICKS            FULL PLATFORM                  │
    │  ┌───────────────────┐              ┌───────────────────────┐       │
    │  │  Projects 5, 7, 8 │              │  Project 4            │       │
    │  │  Delta Lake       │              │  REST API ingest      │       │
    │  │  Unity Catalog    │              │  Parquet → Postgres   │       │
    │  │  dbt-Databricks   │              │  Data quality         │       │
    │  │  RLS + Lineage    │              │  Streamlit dashboard  │       │
    │  └───────────────────┘              └───────────────────────┘       │
    └─────────────────────────────────────────────────────────────────────┘
```

---

## 🔍 Project Deep-Dives

### 🚕 1 · NYC Taxi ELT Pipeline
> [`nyc_taxi_pipeline/`](./nyc_taxi_pipeline)

Loads 3M+ rows of NYC Yellow Taxi trips into PostgreSQL via Python, then runs
dbt to produce two models:
- **`stg_taxi_trips`** — cleaned view (type casts, date filter, quality rules)
- **`fct_trips_daily`** — daily aggregates: trips, revenue, avg distance

```
Parquet → load_raw.py → PostgreSQL (raw) → dbt → staging view → mart table
```

---

### 🥇 2 · Medallion Architecture Pipeline
> [`medallion_pipeline/`](./medallion_pipeline)

Three-task Airflow DAG implementing Bronze / Silver / Gold:

| Layer | What happens |
|-------|-------------|
| Bronze | Raw Parquet copy |
| Silver | Typed, filtered, enriched |
| Gold | Daily aggregates for BI |

```
Raw Parquet → Airflow DAG [Bronze → Silver → Gold] → PostgreSQL
```

---

### ⚡ 3 · Kafka Real-Time Streaming
> [`kafka_streaming/`](./kafka_streaming)

Simulates 1 order/sec from a synthetic e-commerce platform. Producer compresses
messages with gzip and uses `acks="all"`. Consumer prints live revenue stats
every 10 seconds, broken down by product category.

```
producer.py → Kafka (KRaft) → consumer.py → live revenue analytics
```

---

### 🌐 4 · Full Data Platform (Capstone)
> [`capstone/`](./capstone)

End-to-end platform with 4 independently runnable scripts:

| Script | Role |
|--------|------|
| `ingest.py` | Open-Meteo API → `data/weather_raw.parquet` |
| `transform.py` | Clean + enrich → PostgreSQL |
| `quality.py` | 14 assertions; exits 1 on failure |
| `dashboard.py` | Streamlit app: KPIs, charts, filters |

---

### 🔺 5 · Delta Lake Pipeline
> [`delta_lake_pipeline/`](./delta_lake_pipeline)

Medallion Architecture running locally with **PySpark + Delta Lake** — the
same stack used on Databricks at petabyte scale. Demonstrates every key Delta
feature:

| Feature | Script |
|---------|--------|
| Bronze/Silver/Gold writes | `bronze.py`, `silver.py`, `gold.py` |
| OPTIMIZE + ZORDER | `gold.py` |
| Time travel by version | `time_travel.py` |
| Schema evolution (`mergeSchema`) | `time_travel.py` |
| RESTORE, VACUUM (dry run) | `time_travel.py` |

---

### 🌊 6 · Spark Structured Streaming
> [`spark_streaming/`](./spark_streaming)

Production-grade streaming pipeline: Kafka → Spark → Delta Lake.

Key concepts demonstrated:
- **Watermarking** — bounded state, handles late events up to 10 min
- **Tumbling windows** — 1-minute revenue aggregates per category
- **Exactly-once delivery** — checkpoint-based Kafka offset tracking
- **Delta sink** — ACID output queryable while the stream is running

```
Kafka "orders" → Spark readStream → windowed agg → Delta writeStream
```

---

### 🔷 7 · dbt on Databricks
> [`dbt_databricks/`](./dbt_databricks)

The NYC Taxi dbt pipeline re-targeted at a **Databricks SQL Warehouse** with
Unity Catalog. Key upgrades over Project 1:

- `file_format: delta` — all models write Delta tables
- `on_schema_change: merge` — schema evolution without pipeline failures
- `OPTIMIZE ZORDER BY trip_date` — post-hook for data skipping
- Three-level namespace (`main.nyc_taxi_dev.stg_taxi_trips`)
- Photon-accelerated SQL (transparent to dbt)

---

### 🛡️ 8 · Unity Catalog Demo
> [`unity_catalog_demo/`](./unity_catalog_demo)

Three scripts covering the governance layer of the Databricks lakehouse:

| Script | Demonstrates |
|--------|-------------|
| `setup_catalog.py` | Three-level namespace, table creation across Bronze/Silver/Gold |
| `governance.py` | Row-level security (per user group), column masking, data tags |
| `lineage.py` | Column-level lineage graph, impact analysis, upstream/downstream tables |

---

## 🛠️ Skills Demonstrated

| Category | Technologies |
|----------|-------------|
| **Ingestion** | Python `requests`, REST APIs, Parquet, pandas, Auto Loader concept |
| **Batch transformation** | dbt Core, dbt-databricks, SQLAlchemy, PostgreSQL |
| **Lakehouse storage** | Delta Lake (ACID, time travel, Z-ordering, schema evolution) |
| **Orchestration** | Apache Airflow 2.8, Databricks Workflows concept |
| **Streaming** | Apache Kafka (KRaft), kafka-python, Spark Structured Streaming |
| **Governance** | Unity Catalog, row-level security, column masking, lineage |
| **Data quality** | Assertion framework, dbt tests, schema validation |
| **Serving / BI** | Streamlit, Databricks SQL Warehouse, OPTIMIZE ZORDER |
| **Infrastructure** | Docker, Docker Compose, PostgreSQL 15, PySpark |
| **Engineering practices** | Idempotent pipelines, exactly-once streaming, partitioning, checkpointing |

---

## 🗺️ How to Navigate This Repo

```
data-engineering-portfolio/
│
├── nyc_taxi_pipeline/      ← 1: dbt + PostgreSQL ELT
├── medallion_pipeline/     ← 2: Airflow Medallion Architecture
├── kafka_streaming/        ← 3: Real-time Kafka streaming (Python)
├── capstone/               ← 4: Full data platform + Streamlit
│
├── delta_lake_pipeline/    ← 5: Delta Lake Medallion (PySpark)
├── spark_streaming/        ← 6: Spark Structured Streaming → Delta
├── dbt_databricks/         ← 7: dbt targeting Databricks SQL Warehouse
└── unity_catalog_demo/     ← 8: Unity Catalog governance concepts
```

Each subfolder has its own `README.md` with full setup instructions.

---

## ⚡ Quick Starts

### Fastest demo (no Spark needed)
```bash
# Project 4 — full stack with Python only
cd capstone && pip install -r requirements.txt
python ingest.py && python transform.py && python quality.py
streamlit run dashboard.py   # http://localhost:8501
```

### Delta Lake demo (requires Java 11+)
```bash
cd delta_lake_pipeline && pip install -r requirements.txt
curl -L -o data/yellow_tripdata_2024-01.parquet \
  https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet
python bronze.py && python silver.py && python gold.py && python time_travel.py
```

### Governance demo (no Spark needed)
```bash
cd unity_catalog_demo && pip install pandas
python governance.py   # row-level security + column masking
python lineage.py      # column-level lineage graph
```

---

*Built with Python 3.11 · PostgreSQL 15 · Apache Airflow 2.8 · Apache Kafka 7.6 · PySpark 3.5 · Delta Lake 3.0 · dbt 1.8*
