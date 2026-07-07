# 📊 Data Engineering Portfolio

**Vlad Martiniuc** · [GitHub](https://github.com/MartiniucV) · [martiniuc.vladut@gmail.com](mailto:martiniuc.vladut@gmail.com)

14 end-to-end data engineering projects spanning the full modern data stack.
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

### 🏥 Enterprise Analytics — PostgreSQL, dbt, Python, Streamlit

| # | Project | Business Problem | Tech Stack | Folder |
|---|---------|-----------------|------------|--------|
| 14 | 🏥 **MedInsight Analytics** | Romanian private clinic network: 2M appointments, 500k patients, 60 clinics → executive BI platform | PostgreSQL · dbt · Python · Streamlit · scikit-learn | [`medical_data_platform/`](./medical_data_platform) |

---

## 🏛️ Architecture Overview

```
  LOCAL STACK (1–4)          DATABRICKS (5–8)         AZURE + FABRIC (9–13)      ENTERPRISE ANALYTICS (14)
  ─────────────────          ─────────────────         ──────────────────────     ─────────────────────────
  PostgreSQL + dbt           Delta Lake                 Microsoft Fabric           Medallion Architecture
  Airflow DAGs               PySpark + Photon           OneLake + DirectLake       dbt 22-model project
  Kafka Streaming            Unity Catalog              Azure Data Factory         2M row PostgreSQL
  Streamlit Dashboard        Delta Live Tables          Azure Functions            Streamlit + Plotly
                             Structured Streaming       ADLS Gen2 + Delta          scikit-learn + statsmodels
                             AutoLoader                 Databricks on Azure        Revenue forecasting
                                                        Great Expectations         Patient churn ML
                                                        Azure Managed Airflow      Custom quality framework
```

---

## 🔍 Project Deep-Dives

### 🏪 9 · Fabric Lakehouse Simulation
> [`fabric_lakehouse_simulation/`](./fabric_lakehouse_simulation)

RetailCo (200 stores, 2M customers) migrates to Microsoft Fabric.
Simulates OneLake structure, SQL Analytics Endpoint via DuckDB, and
Power BI DirectLake patterns on 200K generated e-commerce orders.

**Key result:** DuckDB GROUP BY on 200K orders in ~40ms — the same query pattern
Fabric's SQL Analytics Endpoint runs on billions of rows via Photon.

---

### 🔄 10 · Azure Data Factory Pipeline Simulation
> [`azure_data_factory_simulation/`](./azure_data_factory_simulation)

FinanceFlow (500K tx/day) consolidates transactions from REST API, CSV drops,
and PostgreSQL replica. Demonstrates Copy Activity, Mapping Data Flow
(velocity-based fraud detection), and Pipeline orchestration with retry + alerts.

**Key result:** The velocity check (simulated) flags customers with > 5
transactions in a 60-minute rolling window — 127 cases in the week-1 test run.

---

### 🏭 11 · Databricks + Azure Integration
> [`databricks_azure_integration/`](./databricks_azure_integration)

ManufactureX IoT pipeline (10K sensors, 28.8M records/day). AutoLoader
with checkpoint-based incremental ingestion, DLT expectations with quarantine
routing, and storage abstraction layer mirroring ADLS Gen2 mount patterns.

**Key result:** Modelled on a common IoT failure mode — bad sensor data reaching
downstream models undetected. DLT `@expect_or_quarantine` routes invalid
readings (8% in the simulated data) to a quarantine table instead.

---

### ⚖️ 12 · Fabric vs. Databricks Comparison
> [`fabric_vs_databricks_comparison/`](./fabric_vs_databricks_comparison)

The same RetailBank transaction pipeline built twice. Fabric wins on cost
and simplicity for BI-centric teams; Databricks wins for ML/streaming.
Includes side-by-side Jupyter notebook and a structured ADR decision framework.

**Key result:** Running both implementations on the same dataset makes the
MERGE vs TRUNCATE difference concrete — the detail that matters most for
incremental pipelines with late-arriving data.

---

### 🌍 13 · End-to-End Azure Pipeline
> [`end_to_end_azure_pipeline/`](./end_to_end_azure_pipeline)

SmartCity AQI monitoring platform built to EU Directive 2008/50/EC.
Every file maps to a real Azure service with cost estimates. Total production
cost: **$188/month** for a pipeline processing 8 stations × 365 days.

**Key result:** The full architecture — API ingest → PySpark transform →
Delta storage lifecycle → Airflow orchestration → Great Expectations quality →
Streamlit dashboard — runs end-to-end with one command: `python orchestration/pipeline_dag.py`

---

### 🏥 14 · MedInsight Analytics Platform
> [`medical_data_platform/`](./medical_data_platform)

A Romanian private healthcare network operating 60 clinics needs a single source
of truth across clinical, financial, and operational data. MedInsight ingests
**2M appointments / 500k patients / 1.4M billing records** (2020–2024), transforms
them through a Bronze→Silver→Gold medallion pipeline, and surfaces everything in a
6-page premium Streamlit dashboard with ML-powered forecasting and churn analysis.

**Key result:** 2M rows loaded into PostgreSQL in **3 minutes** via `COPY`, 22 dbt
models compile in **26 seconds**, and the dashboard returns aggregated KPIs in
**< 3 seconds** — all on a local machine with no cloud required.

Key highlights:
- Full **dbt project**: 7 staging + 5 intermediate + 9 mart models, 29 tests
- **Vectorised data generation**: NumPy replaces Python loops — 2M appointments in ~100s
- **Custom quality framework**: 39 checks (nulls, uniqueness, referential integrity, Z-score anomalies)
- **ML suite**: Holt-Winters revenue forecast, GBT no-show prediction, RFM churn segmentation, Isolation Forest anomaly detection
- **Premium dark dashboard**: glassmorphism KPI cards, medical-red Plotly theme, utilisation gauges

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
| **ML / Analytics** | scikit-learn, statsmodels, Holt-Winters forecasting, Isolation Forest, RFM segmentation |
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
├── ── AZURE + FABRIC ─────────────────────────────
│   ├── fabric_lakehouse_simulation/    ← 9:  Fabric OneLake + DuckDB
│   ├── azure_data_factory_simulation/  ← 10: ADF Copy + Data Flow
│   ├── databricks_azure_integration/   ← 11: AutoLoader + DLT + ADLS
│   ├── fabric_vs_databricks_comparison/← 12: Same pipeline, two ways
│   └── end_to_end_azure_pipeline/      ← 13: Full Azure stack
│
└── ── ENTERPRISE ANALYTICS ───────────────────────
    └── medical_data_platform/          ← 14: MedInsight — 2M rows, dbt, ML, Streamlit
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

*Built with Python 3.11 · PostgreSQL 16 · Apache Airflow 2.8 · Apache Kafka 7.6 ·
PySpark 3.5 · Delta Lake 3.0 · dbt 1.7 · DuckDB 1.5 · Microsoft Fabric · Azure · Streamlit · scikit-learn*
