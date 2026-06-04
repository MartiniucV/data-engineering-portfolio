# 📊 Data Engineering Portfolio

**Vlad Martiniuc** · [GitHub](https://github.com/MartiniucV) · [martiniuc.vladut@gmail.com](mailto:martiniuc.vladut@gmail.com)

A collection of four end-to-end data engineering projects covering the full
spectrum of modern data infrastructure: batch ELT pipelines, medallion
architectures, real-time streaming, and a full data platform with quality
checks and a live dashboard.

---

## 🗂️ Projects

| # | Project | Description | Tech Stack | Folder |
|---|---------|-------------|------------|--------|
| 1 | 🚕 **NYC Taxi ELT Pipeline** | Ingests 3M+ NYC taxi trips, models them with dbt into staging views and a daily-metrics mart | PostgreSQL · dbt Core · Python · pandas | [`nyc_taxi_pipeline/`](./nyc_taxi_pipeline) |
| 2 | 🥇 **Medallion Architecture Pipeline** | Processes taxi data through Bronze → Silver → Gold layers orchestrated by Apache Airflow | Airflow 2.8 · PostgreSQL · pandas · Docker | [`medallion_pipeline/`](./medallion_pipeline) |
| 3 | ⚡ **Kafka Real-Time Streaming** | Simulates an e-commerce order stream; producer publishes to Kafka, consumer surfaces live revenue analytics | Apache Kafka · kafka-python · Faker · Docker | [`kafka_streaming/`](./kafka_streaming) |
| 4 | 🌐 **Full Data Platform (Capstone)** | End-to-end platform: API ingest → Parquet → PostgreSQL → quality checks → Streamlit dashboard | Open-Meteo API · pandas · SQLAlchemy · Streamlit | [`capstone/`](./capstone) |

---

## 🔍 Project Details

### 🚕 1 · NYC Taxi ELT Pipeline
> [`nyc_taxi_pipeline/`](./nyc_taxi_pipeline)

Loads a 50 MB Parquet file of January 2024 NYC Yellow Taxi trips into
PostgreSQL using Python, then runs dbt to produce two models:

- **`stg_taxi_trips`** — casts types, renames columns, filters invalid records
- **`fct_trips_daily`** — daily aggregates: trip count, revenue, average distance

```
Parquet → load_raw.py → PostgreSQL (raw) → dbt → staging → mart
```

---

### 🥇 2 · Medallion Architecture Pipeline
> [`medallion_pipeline/`](./medallion_pipeline)

Implements the Medallion Architecture pattern (Bronze / Silver / Gold) with a
three-task Apache Airflow DAG. Each layer applies progressively stricter
transformations:

| Layer | Storage | What happens |
|-------|---------|--------------|
| Bronze | Parquet | Raw copy, no changes |
| Silver | PostgreSQL | Type casting, null removal, outlier filtering |
| Gold | PostgreSQL | Daily aggregations ready for BI |

```
Raw Parquet → Bronze (copy) → Silver (clean) → Gold (aggregate)
                    └──────── Airflow DAG ────────┘
```

---

### ⚡ 3 · Kafka Real-Time Streaming
> [`kafka_streaming/`](./kafka_streaming)

Simulates an e-commerce platform with ~1 order/second throughput:

- **`producer.py`** — generates synthetic orders with Faker, publishes JSON to the `orders` topic with gzip compression and `acks="all"`
- **`consumer.py`** — reads the topic and prints live revenue stats every 10 seconds broken down by product category

```
producer.py → Kafka (KRaft, single broker) → consumer.py → live analytics
```

---

### 🌐 4 · Full Data Platform (Capstone)
> [`capstone/`](./capstone)

A production-style data platform built around free public weather data:

| Script | Role |
|--------|------|
| `ingest.py` | Calls Open-Meteo API for 5 cities × 90 days → `data/weather_raw.parquet` |
| `transform.py` | Cleans, enriches, idempotently loads → PostgreSQL `weather_daily` |
| `quality.py` | Runs 14 data quality assertions; exits 1 on any failure |
| `dashboard.py` | Interactive Streamlit app with charts, KPIs, and filters |

```
Open-Meteo API → ingest.py → Parquet → transform.py → PostgreSQL
                                                            ↓
                                              quality.py (14 checks)
                                                            ↓
                                            dashboard.py (Streamlit :8501)
```

---

## 🛠️ Skills Demonstrated

| Category | Technologies |
|----------|-------------|
| **Ingestion** | Python `requests`, REST APIs, Parquet, pandas |
| **Batch transformation** | dbt Core (staging + marts), SQLAlchemy, PostgreSQL |
| **Orchestration** | Apache Airflow 2.8 (DAGs, TaskFlow API) |
| **Streaming** | Apache Kafka (KRaft), kafka-python, gzip compression |
| **Data quality** | Assertion-based checks, dbt tests, schema validation |
| **Serving / BI** | Streamlit, SQL aggregations |
| **Infrastructure** | Docker, Docker Compose, PostgreSQL 15 |
| **Engineering practices** | Idempotent pipelines, graceful shutdown, structured logging, `.gitignore` hygiene |

---

## 🗺️ How to Navigate This Repo

```
data-engineering-portfolio/
│
├── nyc_taxi_pipeline/     ← Project 1: dbt + PostgreSQL ELT
│   ├── load_raw.py
│   ├── models/
│   │   ├── staging/
│   │   └── marts/
│   └── dbt_project.yml
│
├── medallion_pipeline/    ← Project 2: Airflow + Medallion Architecture
│   ├── pipeline.py
│   ├── dags/medallion_dag.py
│   └── docker-compose.yml
│
├── kafka_streaming/       ← Project 3: Real-time Kafka streaming
│   ├── producer.py
│   ├── consumer.py
│   └── docker-compose.yml
│
└── capstone/              ← Project 4: Full data platform (capstone)
    ├── ingest.py
    ├── transform.py
    ├── quality.py
    ├── dashboard.py
    └── requirements.txt
```

Each subfolder has its own `README.md` with full setup instructions,
architecture diagrams, and how-to-run steps.

---

## ⚡ Quick Start (Capstone)

The capstone project is the fastest way to see the full stack in action —
it only requires PostgreSQL and Python:

```bash
cd capstone
pip install -r requirements.txt

python ingest.py                   # fetch 90 days of weather data
python transform.py                # clean and load into PostgreSQL
python quality.py                  # validate (should print 14 PASS lines)
streamlit run dashboard.py         # open http://localhost:8501
```

---

*Built with Python 3.11 · PostgreSQL 15 · Apache Airflow 2.8 · Apache Kafka 7.6*
