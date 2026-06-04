# NYC Taxi Pipeline — dbt + PostgreSQL

An analytics pipeline that models NYC Yellow Taxi trip data using dbt, producing
clean staging views and an aggregated daily-metrics mart backed by PostgreSQL.

## Architecture

```
Raw CSV / API
     │
     ▼
load_raw.py  ─────────────────────▶  PostgreSQL (public.raw_taxi_trips)
                                              │
                              ┌───────────────┘
                              │   dbt run
                              ▼
                    models/staging/stg_taxi_trips   (view)
                              │
                              ▼
                    models/marts/fct_trips_daily    (table)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Raw ingestion | Python + pandas |
| Transformation | dbt 1.x |
| Storage | PostgreSQL 15 |
| Testing / docs | dbt tests + dbt docs |

## Project Structure

```
nyc_taxi_pipeline/
├── load_raw.py                  # Loads raw parquet into PostgreSQL
├── dbt_project.yml
├── models/
│   ├── staging/
│   │   ├── stg_taxi_trips.sql   # Casts, renames, basic filters
│   │   └── schema.yml           # Source definitions + not-null tests
│   └── marts/
│       └── fct_trips_daily.sql  # Daily aggregates (trips, revenue, distance)
├── analyses/
├── macros/
├── seeds/
├── snapshots/
└── tests/
```

## Models

### `stg_taxi_trips` (staging view)
Cleans the raw table: casts timestamps, filters out zero-distance / negative-fare
rows, and standardises column names.

### `fct_trips_daily` (mart table)
Aggregates per calendar day:
- `total_trips` — trip count
- `total_revenue` — sum of `total_amount`
- `avg_trip_distance` — mean distance in miles
- `avg_fare` — mean fare amount

## How to Run

### 1. Load raw data into PostgreSQL

```bash
python load_raw.py
```

### 2. Run dbt models

```bash
dbt run
```

### 3. Run dbt tests

```bash
dbt test
```

### 4. Generate & serve docs

```bash
dbt docs generate
dbt docs serve   # opens http://localhost:8080
```

## Prerequisites

- Python 3.9+
- PostgreSQL running on `localhost:5432`
- dbt-postgres: `pip install dbt-postgres`
- Configure `~/.dbt/profiles.yml` with a `nyc_taxi_pipeline` profile targeting your database
