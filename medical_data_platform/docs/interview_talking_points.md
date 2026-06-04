# MedInsight Analytics Platform — Interview Guide

## Project Elevator Pitch (30 seconds)

> "I built MedInsight Analytics Platform, a production-grade healthcare data engineering
> project modelled after a Romanian private clinic network. It processes 20,000 appointments
> across 50 doctors and 5,000 patients using a Medallion architecture: Python for ingestion,
> dbt for transformation, PostgreSQL as the warehouse, and Streamlit for a 6-page executive
> dashboard. I also implemented ML models for revenue forecasting, churn prediction, and
> no-show risk scoring."

---

## Core Data Engineering Concepts Demonstrated

### 1. Medallion Architecture
**Q: "What is a medallion architecture and why did you use it?"**

A: Three-layer pattern:
- **Bronze** — immutable raw data snapshots (Parquet). Never modified after write.
- **Silver** — cleaned, validated, deduped data. Type enforcement, business rule validation.
- **Gold** — analytics-optimised models built by dbt. Fact/dimension tables for BI consumption.

Benefits: clear data lineage, ability to replay from bronze, separation of concerns, isolated blast radius when bugs introduced.

### 2. dbt Models
**Q: "Walk me through your dbt project structure."**

A: Three model tiers following standard patterns:
- `stg_*` — thin views, source cleanup only, type casting, naming convention enforcement
- `int_*` — business logic, joins between entities, derived metrics
- `fct_*/dim_*` — materialised tables, window functions, aggregations, final analytics surfaces

All models have: `not_null`, `unique`, `accepted_values`, and `relationships` tests.

### 3. Slowly Changing Dimensions
**Q: "How did you handle doctor dimension changes?"**

A: Implemented SCD Type 1 in `dim_doctors` (current state only). The snapshot model in `dbt/snapshots/` tracks historical changes for Type 2 audit needs. In production: doctors changing specialty or clinic would generate a new SCD2 row while keeping the original for historical appointment attribution.

### 4. Incremental Loading
**Q: "How does your pipeline handle incremental loads?"**

A: Current implementation uses idempotent TRUNCATE + full reload (suitable for 20K rows). For production scale:
- PostgreSQL: incremental dbt models filtering on `loaded_at > last_run_ts`
- Partitioned tables by month for efficient time-range scans
- BRIN indexes on timestamp columns for sequential scans

### 5. Data Quality
**Q: "How do you validate data quality?"**

A: Two layers:
1. **dbt tests** — declarative checks at model level (uniqueness, nulls, referential integrity)
2. **Custom Python framework** (`quality_checks.py`) — null rates, range validation, z-score anomaly detection, freshness checks, referential integrity at row level

Quality report saved as JSON, exit code 1 on failures for CI integration.

---

## Technology Choices

| Choice | Alternatives Considered | Why This |
|--------|------------------------|---------|
| PostgreSQL | BigQuery, Snowflake | Free, local, PostgreSQL expertise ubiquitous |
| dbt-core | raw SQL scripts | Version control, tests, docs, lineage built-in |
| Streamlit | Superset, Metabase | Pure Python, fast iteration, full customisation |
| Parquet | CSV only | Columnar storage, ~3x smaller, schema enforcement |
| Loguru | Python logging | Clean API, structured output, no boilerplate |
| pydantic-settings | dotenv + os.environ | Type safety, validation, IDE autocomplete |

---

## Business Metrics Defined

| Metric | Definition | Why It Matters |
|--------|-----------|----------------|
| Completion Rate | completed / total | Primary efficiency KPI |
| No-Show Rate | no_show / total | Revenue loss indicator |
| Cancellation Rate | cancelled / total | Demand planning signal |
| LTV | ΣNet Revenue / patient | Retention investment prioritisation |
| Avg Wait Time | Mean(waiting_time_minutes) | Patient satisfaction driver |
| Revenue Per Active Day | Total Revenue / Active Days | Doctor ROI |
| Churn Risk | Days since last visit > 180 | Retention campaign trigger |

---

## Challenges & Solutions

### Challenge: Realistic data distribution
**Solution**: Used `np.random.exponential` for patient visit frequency (power law distribution — most patients visit 1-3 times, a few visit 20+). Seasonal weights for appointment volume. Z-score-based anomaly injection for 15% of lab results.

### Challenge: Idempotent pipeline
**Solution**: TRUNCATE + reload pattern with proper FK ordering. Could also use `ON CONFLICT DO NOTHING` for upserts in streaming scenarios.

### Challenge: Dashboard performance
**Solution**: Streamlit `@st.cache_data(ttl=300)` on all SQL queries. PostgreSQL materialized views for the two most expensive aggregations (monthly revenue, doctor performance).

---

## Scalability Roadmap

```
Current (Portfolio)          Production (100M rows)      Enterprise (1B+)
────────────────────        ──────────────────────       ──────────────────
Python CSV → Postgres        Kafka → Flink → PG          Kafka → Spark → 
dbt-core local               dbt Cloud + Airflow          BigQuery/Snowflake
Streamlit                    Metabase/Looker              Tableau/PowerBI
5K patients / 20K appts      500K patients / 2M appts    50M patients / 200M appts
```
