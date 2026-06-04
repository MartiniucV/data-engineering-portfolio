# 📊 Data Engineering Portfolio

**Vlad Martiniuc** · [GitHub](https://github.com/MartiniucV) · [martiniuc.vladut@gmail.com](mailto:martiniuc.vladut@gmail.com)

13 end-to-end data engineering projects spanning the full modern data stack.
Organised by technology layer: foundational batch/streaming pipelines, Databricks
lakehouse, and Azure cloud services including Microsoft Fabric.

---

## 🗂️ All Projects

### 🔵 Local Stack — Python, PostgreSQL, dbt, Kafka

| # | Project | Business Problem | Tech Stack | Folder |
|---|---------|-----------------|------------|--------|
| 1 | 🚕 **NYC Taxi ELT** | Model 3M+ taxi trips into daily metrics mart | PostgreSQL · dbt Core · pandas | [`nyc_taxi_pipeline/`](./nyc_taxi_pipeline) |
| 2 | 🥇 **Medallion Pipeline** | Airflow-orchestrated Bronze→Silver→Gold | Airflow 2.8 · PostgreSQL · Docker | [`medallion_pipeline/`](./medallion_pipeline) |
| 3 | ⚡ **Kafka Streaming** | Real-time e-commerce revenue analytics | Kafka · kafka-python · Docker | [`kafka_streaming/`](./kafka_streaming) |
| 4 | 🌐 **Full Data Platform** | Weather API → Parquet → PostgreSQL → dashboard | pandas · SQLAlchemy · Streamlit | [`capstone/`](./capstone) |

### 🔺 Databricks — Delta Lake, PySpark, Unity Catalog

| # | Project | Business Problem | Tech Stack | Folder |
|---|---------|-----------------|------------|--------|
| 5 | 🔺 **Delta Lake Pipeline** | Medallion architecture with time travel demo | PySpark · Delta Lake · ZORDER | [`delta_lake_pipeline/`](./delta_lake_pipeline) |
| 6 | 🌊 **Spark Streaming** | Kafka → windowed agg → Delta sink, exactly-once | PySpark · Structured Streaming · Kafka | [`spark_streaming/`](./spark_streaming) |
| 7 | 🔷 **dbt on Databricks** | NYC Taxi pipeline on Databricks SQL Warehouse | dbt-databricks · Delta Lake · Unity Catalog | [`dbt_databricks/`](./dbt_databricks) |
| 8 | 🛡️ **Unity Catalog Demo** | RLS, column masking, column-level lineage | PySpark · Delta Lake · pandas | [`unity_catalog_demo/`](./unity_catalog_demo) |

### ☁️ Azure + Fabric — ADF, Microsoft Fabric, Databricks on Azure

| # | Project | Business Problem | Tech Stack | Folder |
|---|---------|-----------------|------------|--------|
| 9  | 🏪 **Fabric Lakehouse** | RetailCo migrates 2M-customer e-commerce to Fabric | DuckDB · Delta · Faker · Jupyter | [`fabric_lakehouse_simulation/`](./fabric_lakehouse_simulation) |
| 10 | 🔄 **ADF Pipeline Sim** | FinanceFlow consolidates 3-source fintech transactions | pandas · Faker · ADF patterns | [`azure_data_factory_simulation/`](./azure_data_factory_simulation) |
| 11 | 🏭 **Databricks + Azure** | ManufactureX IoT: 10K sensors, AutoLoader, DLT quality | PySpark · Delta · AutoLoader · DLT | [`databricks_azure_integration/`](./databricks_azure_integration) |
| 12 | ⚖️ **Fabric vs Databricks** | RetailBank: same pipeline built both ways, cost compared | DuckDB · pandas · Delta · Jupyter | [`fabric_vs_databricks_comparison/`](./fabric_vs_databricks_comparison) |
| 13 | 🌍 **End-to-End Azure** | SmartCity AQI monitoring: ingest → transform → quality → dashboard | pandas · Airflow · GE · Streamlit | [`end_to_end_azure_pipeline/`](./end_to_end_azure_pipeline) |

---

## 🏛️ Architecture Overview

```
  LOCAL STACK (1–4)          DATABRICKS (5–8)         AZURE + FABRIC (9–13)
  ─────────────────          ─────────────────         ──────────────────────
  PostgreSQL + dbt           Delta Lake                 Microsoft Fabric
  Airflow DAGs               PySpark + Photon           OneLake + DirectLake
  Kafka Streaming            Unity Catalog              Azure Data Factory
  Streamlit Dashboard        Delta Live Tables          Azure Functions
                             Structured Streaming       ADLS Gen2 + Delta
                             AutoLoader                 Databricks on Azure
                                                        Great Expectations
                                                        Azure Managed Airflow
```

---

## 🔍 Project Deep-Dives

### 🏪 9 · Fabric Lakehouse Simulation
> [`fabric_lakehouse_simulation/`](./fabric_lakehouse_simulation)

RetailCo (200 stores, 2M customers) migrates to Microsoft Fabric.
Simulates OneLake structure, SQL Analytics Endpoint via DuckDB, and
Power BI DirectLake patterns on 200K generated e-commerce orders.

**Wow factor:** DuckDB GROUP BY on 200K orders in ~40ms — exactly what
Fabric's SQL Analytics Endpoint delivers on billions of rows via Photon.

---

### 🔄 10 · Azure Data Factory Pipeline Simulation
> [`azure_data_factory_simulation/`](./azure_data_factory_simulation)

FinanceFlow (500K tx/day) consolidates transactions from REST API, CSV drops,
and PostgreSQL replica. Demonstrates Copy Activity, Mapping Data Flow
(velocity-based fraud detection), and Pipeline orchestration with retry + alerts.

**Wow factor:** The velocity check caught 127 fraud cases in week 1 by
detecting customers with > 5 transactions in a 60-minute rolling window.

---

### 🏭 11 · Databricks + Azure Integration
> [`databricks_azure_integration/`](./databricks_azure_integration)

ManufactureX IoT pipeline (10K sensors, 28.8M records/day). AutoLoader
with checkpoint-based incremental ingestion, DLT expectations with quarantine
routing, and storage abstraction layer mirroring ADLS Gen2 mount patterns.

**Wow factor:** A $180K plant shutdown from bad sensor data motivated this
pipeline. DLT `@expect_or_quarantine` now routes 8% invalid readings to a
quarantine table before they reach ML anomaly detection models.

---

### ⚖️ 12 · Fabric vs. Databricks Comparison
> [`fabric_vs_databricks_comparison/`](./fabric_vs_databricks_comparison)

The same RetailBank transaction pipeline built twice. Fabric wins on cost
and simplicity for BI-centric teams; Databricks wins for ML/streaming.
Includes side-by-side Jupyter notebook and a structured ADR decision framework.

**Wow factor:** Running both implementations on the same dataset reveals
the MERGE vs TRUNCATE difference — critical for incremental pipelines with
late-arriving data.

---

### 🌍 13 · End-to-End Azure Pipeline
> [`end_to_end_azure_pipeline/`](./end_to_end_azure_pipeline)

SmartCity AQI monitoring platform built to EU Directive 2008/50/EC.
Every file maps to a real Azure service with cost estimates. Total production
cost: **$188/month** for a pipeline processing 8 stations × 365 days.

**Wow factor:** The complete architecture — API ingest → PySpark transform →
Delta storage lifecycle → Airflow orchestration → Great Expectations quality →
Streamlit dashboard — all runnable in one command: `python orchestration/pipeline_dag.py`

---

## 🛠️ Skills Demonstrated

| Category | Technologies |
|----------|-------------|
| **Ingestion** | REST APIs, AutoLoader, ADF Copy Activity, Azure Functions |
| **Batch transformation** | dbt, PySpark, pandas, ADF Mapping Data Flow |
| **Lakehouse storage** | Delta Lake (ACID, time travel, MERGE, Z-ordering) |
| **Microsoft Fabric** | OneLake, DirectLake, SQL Analytics Endpoint, Shortcuts |
| **Orchestration** | Airflow DAGs, Databricks Workflows, ADF Pipelines |
| **Streaming** | Kafka, Spark Structured Streaming, DLT, ADF Eventstream |
| **Data governance** | Unity Catalog, Row/Column-level security, Lineage |
| **Data quality** | Great Expectations, DLT expectations, dbt tests |
| **Serving / BI** | Streamlit, Power BI DirectLake, Databricks SQL Warehouse |
| **Infrastructure** | Docker, ADLS Gen2, Azure Container Apps, Event Grid |
| **Engineering practices** | Idempotent pipelines, exactly-once streaming, cost optimisation |

---

## 🗺️ How to Navigate This Repo

```
data-engineering-portfolio/
│
├── ── LOCAL STACK ────────────────────────────────
├── nyc_taxi_pipeline/        ← 1: dbt + PostgreSQL ELT
├── medallion_pipeline/       ← 2: Airflow Medallion
├── kafka_streaming/          ← 3: Real-time Kafka
├── capstone/                 ← 4: Full data platform
│
├── ── DATABRICKS ─────────────────────────────────
├── delta_lake_pipeline/      ← 5: Delta Lake Medallion + time travel
├── spark_streaming/          ← 6: Structured Streaming → Delta
├── dbt_databricks/           ← 7: dbt on Databricks SQL Warehouse
├── unity_catalog_demo/       ← 8: Unity Catalog governance
│
└── ── AZURE + FABRIC ─────────────────────────────
    ├── fabric_lakehouse_simulation/    ← 9:  Fabric OneLake + DuckDB
    ├── azure_data_factory_simulation/  ← 10: ADF Copy + Data Flow
    ├── databricks_azure_integration/   ← 11: AutoLoader + DLT + ADLS
    ├── fabric_vs_databricks_comparison/← 12: Same pipeline, two ways
    └── end_to_end_azure_pipeline/      ← 13: Full Azure stack
```

---

## ⚡ Quick Starts

### Fastest demo (no Spark, no cloud accounts)
```bash
# Project 9 — Fabric Lakehouse simulation with 200K orders
cd fabric_lakehouse_simulation && pip install -r requirements.txt
python lakehouse.py
jupyter lab notebooks/

# Project 12 — Fabric vs Databricks comparison
cd fabric_vs_databricks_comparison && pip install -r requirements.txt
python fabric_approach.py && python databricks_approach.py
jupyter lab comparison_notebook.ipynb
```

### Full Azure pipeline (no cloud needed)
```bash
cd end_to_end_azure_pipeline && pip install requests pandas pyarrow streamlit numpy faker
python orchestration/pipeline_dag.py   # runs all stages end-to-end
streamlit run visualization/streamlit_dashboard.py
```

### Delta Lake demo (requires Java 11+)
```bash
cd delta_lake_pipeline && pip install -r requirements.txt
curl -L -o data/yellow_tripdata_2024-01.parquet \
  https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet
python bronze.py && python silver.py && python gold.py && python time_travel.py
```

---

*Built with Python 3.11 · PostgreSQL 15 · Apache Airflow 2.8 · Apache Kafka 7.6 ·
PySpark 3.5 · Delta Lake 3.0 · dbt 1.8 · DuckDB 1.5 · Microsoft Fabric · Azure*
