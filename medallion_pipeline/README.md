# Medallion Architecture Pipeline

## Overview
End-to-end data pipeline implementing the Medallion Architecture using Apache Airflow. Processes NYC Taxi trip data through Bronze, Silver, and Gold layers.

## Architecture

```
Raw Parquet File -> Bronze (raw copy) -> Silver (cleaned, filtered) -> Gold (daily metrics)
```

## Tech Stack
- Apache Airflow 2.8.0 - orchestration via Docker Compose
- PostgreSQL 15 - Silver and Gold storage
- Python + pandas - data transformations
- Docker - containerized Airflow stack

## Files

| File | Purpose |
|------|---------|
| `pipeline.py` | Bronze/Silver/Gold transformations, runnable standalone |
| `dags/medallion_dag.py` | Airflow DAG wrapping the same pipeline |
| `docker-compose.yml` | Airflow + PostgreSQL stack |

## How to Run

```bash
# Orchestrated via Airflow
docker compose up -d
# Airflow UI: http://localhost:8080 (airflow/airflow)

# Or run each layer manually
python pipeline.py bronze
python pipeline.py silver
python pipeline.py gold
```
