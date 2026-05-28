# NYC Taxi ELT Pipeline 🚕

## Overview
End-to-end ELT pipeline processing 3M+ real NYC taxi trips from January 2024.
Raw data lands in PostgreSQL, gets cleaned and transformed with dbt,
and surfaces daily revenue and trip metrics ready for analysis.

## Architecture
Parquet File (50MB)
↓
Python ingest (load_raw.py)
↓
PostgreSQL — raw_taxi_trips (3M rows)
↓
dbt staging — stg_taxi_trips (cleaned, filtered)
↓
dbt marts — fct_trips_daily (31 rows, daily metrics)

## Tech Stack
- **PostgreSQL 15** — data warehouse
- **dbt Core 1.8** — transformations & lineage
- **Python + pandas** — data ingestion
- **Docker** — local Postgres instance
- **DBeaver** — SQL exploration
- **GitHub** — version control

## Key Insights
- 📅 Most trips: January 27, 2024
- 💰 Highest revenue: January 25, 2024
- 🧹 Filtered invalid records (dates from 2002, 2009)

## How to run
1. Start Postgres: `docker start postgres-local`
2. Load raw data: `python load_raw.py`
3. Run dbt models: `cd nyc_taxi_pipeline && dbt run`
