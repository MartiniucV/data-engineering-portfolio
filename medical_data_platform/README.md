# MedInsight Analytics Platform

> **Enterprise Healthcare Data Engineering Portfolio Project**
> A production-grade data platform modelled after a Romanian private healthcare network.

---

## Business Context

A Romanian private healthcare network operating six clinics across **Cluj-Napoca, București,
Timișoara, Iași, Brașov, and Constanța** needs a centralised analytics platform to:

- Monitor clinic-level financial performance and YoY growth
- Track doctor productivity, utilisation rates, and patient satisfaction
- Reduce appointment no-shows and cancellations (currently ~23% combined)
- Segment patients by lifetime value for targeted retention campaigns
- Forecast monthly revenue to support quarterly planning
- Provide real-time operational dashboards for clinic managers

The platform ingests, transforms, and serves ~20,000 appointment records per year across
50 doctors and 5,000 active patients.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                       MedInsight Analytics Platform                              │
│                                                                                  │
│   GENERATE          BRONZE           SILVER         GOLD/MARTS      SERVING     │
│  ──────────      ──────────       ──────────      ──────────────   ──────────   │
│  Faker +         Raw Parquet  →   Cleaned &   →   dbt models  →   Streamlit    │
│  Python          (Bronze/)        validated       (analytics       Dashboard    │
│  scripts                          Parquet         schema)                       │
│                                   (Silver/)                        ML Models    │
│                                                                                  │
│  PostgreSQL schemas: raw | staging | intermediate | analytics                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Medallion Architecture

| Layer | Location | Description |
|-------|----------|-------------|
| **Bronze** | `data/bronze/*.parquet` | Raw Parquet snapshots of generated data. Immutable. |
| **Silver** | `data/silver/*.parquet` | Cleaned, deduplicated, type-enforced datasets. |
| **Gold** | `analytics.*` (PostgreSQL) | dbt-built fact + dimension tables optimised for BI. |

---

## Data Model

```
clinics ──< doctors ──< appointments >── patients
                 └──────────────────< services
                                 └──< billing
                                 └──< prescriptions
                                 └──< lab_results
```

### Key Tables

| Table | Rows | Description |
|-------|------|-------------|
| `fct_appointments` | 20,000 | Core fact table with enriched appointment details |
| `fct_daily_revenue` | ~1,400 | Aggregated daily revenue by city & specialty |
| `fct_doctor_performance` | 50 | Per-doctor KPIs with rankings |
| `fct_patient_retention` | ~500 | Cohort-based monthly retention rates |
| `dim_doctors` | 50 | Doctor dimension with SCD Type 1 attributes |
| `dim_patients` | 5,000 | Patient dimension with RFM & churn scores |
| `dim_clinics` | 6 | Clinic dimension with aggregated metrics |
| `dim_services` | 16 | Medical services catalogue |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Data Generation | Python 3.11, Faker (ro_RO), NumPy |
| Data Processing | Pandas, Polars, PyArrow |
| Data Warehouse | PostgreSQL 16 |
| Transformation | dbt-core 1.7, dbt-postgres |
| Analytics/ML | scikit-learn, statsmodels, DuckDB |
| Dashboard | Streamlit, Plotly |
| Configuration | pydantic-settings, python-dotenv, PyYAML |
| Logging | Loguru, Rich |
| Testing | pytest, pytest-cov |
| Dev Tooling | Docker Compose, Makefile |

---

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 16 (local or Docker)

### Option A: Docker (recommended)

```bash
# 1. Clone and navigate
git clone <repo> && cd medical_data_platform

# 2. Start PostgreSQL
docker-compose up -d postgres

# 3. Setup virtual environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 4. Run the full pipeline
python scripts/run_pipeline.py

# 5. Launch dashboard
streamlit run dashboard/dashboard.py
```

### Option B: Existing PostgreSQL

```bash
# 1. Copy and edit environment
cp .env.example .env
# Edit .env with your DB credentials

# 2. Install dependencies
pip install -r requirements.txt

# 3. Generate synthetic data
python scripts/generate_data.py

# 4. Load to PostgreSQL
python scripts/load_postgres.py

# 5. Run dbt models
cd dbt && dbt deps && dbt run --profiles-dir . && dbt test --profiles-dir .

# 6. Run quality checks
python scripts/quality_checks.py

# 7. Run forecasting models
python scripts/forecasting.py

# 8. Launch dashboard
streamlit run dashboard/dashboard.py
```

### Using Make

```bash
make setup      # Create venv + install deps
make generate   # Generate synthetic data
make load       # Load to PostgreSQL
make dbt-run    # Run dbt models
make quality    # Run quality checks
make dashboard  # Launch Streamlit
make all        # Everything end-to-end
```

---

## Dashboard Pages

| Page | Key Metrics |
|------|-------------|
| 📊 Executive Overview | Total revenue, YoY growth, clinic comparison, appointment status mix |
| 👨‍⚕️ Doctor Performance | Revenue ranking, completion rates, avg rating, heatmaps |
| 👤 Patient Analytics | Demographics, cohort retention, LTV, churn risk, geography |
| 💰 Financial Analytics | Revenue trends, service profitability, payment methods |
| ⚙️ Operational Metrics | Cancellation rates, no-shows by channel/DOW, wait time heatmap |
| 🔮 Predictive Analytics | 6-month revenue forecast, no-show risk factors, anomaly detection |

---

## dbt Project Structure

```
dbt/
├── models/
│   ├── staging/       # stg_*: light cleaning, type casting
│   ├── intermediate/  # int_*: business logic, joins
│   └── marts/         # fct_* + dim_*: analytics-ready tables
├── macros/            # safe_divide, generate_surrogate_key
├── snapshots/         # SCD Type 2 for doctors
├── tests/             # Custom singular tests
└── sources.yml        # Raw schema source definitions
```

---

## Data Quality Framework

Custom Python quality framework in `scripts/quality_checks.py`:

- **Null checks** — max 2% null rate on critical columns
- **Uniqueness** — zero duplicates on primary keys
- **Referential integrity** — < 1% orphan records
- **Range checks** — ages 0–120, ratings 1–5, prices ≥ 0
- **Accepted values** — status, gender, payment_status
- **Statistical anomalies** — Z-score > 3.5 flagged
- **Freshness** — validates data currency

Results exported to `data/exports/quality_report.json`.

---

## Advanced Analytics

| Module | Technique | Output |
|--------|-----------|--------|
| Revenue Forecasting | Holt-Winters ETS | 6-month revenue projection |
| No-Show Prediction | Gradient Boosted Trees | Feature importance + AUC score |
| Patient Churn | RFM + Logistic Regression | Churn probability + segments |
| Cohort Retention | Cohort pivot analysis | Monthly retention matrix |
| Anomaly Detection | Isolation Forest | Billing anomaly flags |
| Doctor Utilization | Aggregation + ranking | Utilization rate report |

---

## Sample Analytics Queries

```sql
-- Top 5 doctors by 2024 revenue growth
SELECT full_name, specialty,
       revenue_2023, revenue_2024,
       ROUND((revenue_2024 / NULLIF(revenue_2023, 0) - 1) * 100, 1) AS yoy_pct
FROM analytics.fct_doctor_performance
ORDER BY yoy_pct DESC NULLS LAST
LIMIT 5;

-- Patient retention by cohort (first 3 months)
SELECT TO_CHAR(cohort_month, 'YYYY-MM') AS cohort,
       period_number,
       ROUND(retention_rate * 100, 1)   AS retention_pct
FROM analytics.fct_patient_retention
WHERE period_number <= 3
ORDER BY cohort_month, period_number;

-- Clinics with highest no-show rates
SELECT clinic_city, ROUND(AVG(no_show_rate) * 100, 1) AS avg_noshw_pct
FROM analytics.fct_operational_efficiency
GROUP BY clinic_city
ORDER BY avg_noshw_pct DESC;
```

---

## Interview Talking Points

### Architecture Decisions

1. **Medallion Architecture** — Chose Bronze/Silver/Gold layers to separate raw ingestion from
   business logic. This makes debugging straightforward: trace data issues back to the exact
   transformation step.

2. **dbt for transformations** — dbt provides version-controlled, tested SQL transformations with
   automatic lineage. Every model has tests (uniqueness, not_null, accepted_values, relationships).

3. **PostgreSQL materialized views** — For frequently-queried aggregations (monthly revenue,
   doctor performance), materialized views provide sub-second query time without OOM risks.

4. **Incremental design** — `load_postgres.py` uses TRUNCATE + reload for idempotency. In
   production, this would be replaced with CDC (Debezium) + incremental dbt models.

### Scalability Considerations

- Partition `raw.appointments` by `scheduled_at` month for tables > 100M rows
- Replace Python CSVs with Kafka + Flink for streaming ingestion
- Move to dbt Cloud + Snowflake/BigQuery for petabyte scale
- Add Airflow/Prefect DAGs for scheduling

### What I'd improve with more time

- **SCD Type 2** for doctor dimension (doctor moves clinic, changes specialty)
- **Real-time streaming** with Kafka → Flink → PostgreSQL
- **CI/CD pipeline** with GitHub Actions: lint → test → dbt compile → deploy
- **Feature store** for ML models using Feast
- **Row-level security** in PostgreSQL for GDPR compliance
- **Alerting** when KPIs deviate from forecast (PagerDuty integration)

---

## Project Structure

```
medical_data_platform/
├── data/{raw,bronze,silver,gold,exports}/
├── scripts/
│   ├── generate_data.py       # Synthetic data generator
│   ├── load_postgres.py       # PostgreSQL loader with DDL
│   ├── transform_data.py      # Bronze → Silver transformer
│   ├── quality_checks.py      # Data quality framework
│   ├── run_pipeline.py        # Pipeline orchestrator
│   ├── forecasting.py         # ML & forecasting models
│   └── seed_reference_tables.py
├── dbt/                       # Full dbt project (7 staging + 5 int + 8 mart models)
├── dashboard/
│   ├── dashboard.py           # Streamlit entry point
│   ├── pages/                 # 6 dashboard pages
│   ├── components/            # Reusable DB, chart, filter components
│   └── assets/style.css       # Dark healthcare theme
├── sql/{ddl,analytics,optimization}/
├── tests/{unit,integration,data_quality}/
├── config/                    # Settings, YAML config
├── docs/                      # Architecture & data dictionary
└── docker-compose.yml
```

---

*Built with Python 3.11 · PostgreSQL 16 · dbt-core 1.7 · Streamlit 1.33*
*MedInsight Analytics Platform — Portfolio Project by Martiniuc Vlad*
