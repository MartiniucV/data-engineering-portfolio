# Medallion Architecture Pipeline

## Overview
End-to-end data pipeline implementing the Medallion Architecture using Apache Airflow. Processes NYC Taxi trip data through Bronze, Silver, and Gold layers.

## Architecture
Raw Parquet File -> Bronze (raw copy) -> Silver (cleaned, filtered) -> Gold (daily metrics)

## Tech Stack
- Apache Airflow 2.8.0 - orchestration via Docker Compose
- PostgreSQL 15 - Silver and Gold storage
- Python + pandas - data transformations
- Docker - containerized Airflow stack

## How to Run
Start Airflow: docker compose up -d
Run manually: python pipeline.py bronze / silver / gold
Airflow UI: http://localhost:8080 (airflow/airflow)
