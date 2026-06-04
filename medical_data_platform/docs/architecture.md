# MedInsight Analytics Platform — Architecture

## Overview

MedInsight implements a **Medallion Architecture** (Bronze → Silver → Gold) on PostgreSQL,
orchestrated by Python scripts and dbt. The serving layer is a Streamlit multi-page dashboard.

## Layer Definitions

### Bronze Layer — Raw Snapshots

- **Location:** `data/bronze/*.parquet` (partitioned by year for appointments)
- **Format:** Apache Parquet, Snappy compression
- **Immutability:** Files are never modified after write — re-runs recreate them
- **Purpose:** Audit trail, replay capability, decoupling of ingestion from transformation

### Silver Layer — Cleaned Data

- **Location:** `data/silver/*.parquet`
- **Transformations applied:** `scripts/transform_data.py`
  - Type enforcement (dates, numerics, booleans)
  - Null handling and deduplication
  - Derived columns (age_band, risk_category, seniority_band)
  - Range clipping (ages 0–120, ratings 1–5)

### Gold Layer — Analytics Marts

- **Location:** PostgreSQL `analytics` schema (dbt-managed)
- **Models:** 9 materialised tables (5 facts + 4 dimensions)
- **Refresh:** Re-run `dbt run` after any raw data update

## PostgreSQL Schema Design

```
raw          — 9 tables: direct CSV load via COPY
staging      — dbt staging views (stg_*)
intermediate — dbt intermediate views (int_*)
analytics    — dbt mart tables (fct_* + dim_*)
warehouse    — reference tables (dim_calendar)
```

## Data Flow

```
generate_data.py
  └─► data/raw/*.csv          (human-readable snapshots)
  └─► data/bronze/*.parquet   (typed, compressed)

load_postgres.py
  └─► raw.*                   (PostgreSQL COPY, ~3 min for 2M rows)

transform_data.py
  └─► data/silver/*.parquet   (cleaned, enriched)

dbt run
  └─► staging.*               (views — minimal transformations)
  └─► intermediate.*          (views — business logic)
  └─► analytics.*             (tables — final marts)

Streamlit
  └─► queries analytics.*     (server-side aggregation, cached 5 min)
```

## Performance Design Decisions

| Decision | Rationale |
|----------|-----------|
| PostgreSQL COPY for bulk loading | 10–50× faster than INSERT for >10k rows |
| Vectorised NumPy appointment generation | Avoids 2M Python loop iterations |
| dbt models aggregated in SQL | Never pulls full tables into Python/Pandas |
| `@st.cache_data(ttl=300)` on every query | Dashboard stays responsive across page navigations |
| fct_operational_efficiency at monthly grain | Window functions over 2M rows exceeded PostgreSQL shared memory |
| Partitioned Parquet by year | Enables year-filtered scans on large appointment history |

## Security Considerations (production hardening)

- `.env` file excluded from git via `.gitignore`
- Profiles `dbt/profiles.yml` generated at runtime, also gitignored
- No credentials hardcoded in any Python or SQL file
- GDPR: CNP values are synthetic — no real personal data
- Row-level security (per-clinic isolation) is a documented future improvement
