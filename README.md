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
