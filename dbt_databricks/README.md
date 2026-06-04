# dbt on Databricks — NYC Taxi Pipeline

The same NYC Taxi ELT pipeline as Project 1 (`nyc_taxi_pipeline/`), rebuilt
to target a **Databricks SQL Warehouse** via the `dbt-databricks` adapter.
Demonstrates how dbt integrates with the Databricks lakehouse: Delta Lake
format, Unity Catalog three-level namespace, and Photon-accelerated SQL.

---

## Architecture

```
Data Source
  └── Auto Loader / COPY INTO  ──▶  main.raw.taxi_trips (Unity Catalog)
                                              │
                                              │  dbt run
                                              ▼
                              main.nyc_taxi_dev.staging.stg_taxi_trips (view)
                                              │
                                              ▼
                              main.nyc_taxi_dev.marts.fct_trips_daily  (Delta table)
                                              │
                                              ▼
                              Power BI / Tableau / Databricks SQL
```

---

## Key Differences from Project 1 (PostgreSQL)

| Aspect | Project 1 (PostgreSQL) | This Project (Databricks) |
|--------|------------------------|--------------------------|
| Storage format | PostgreSQL heap tables | Delta Lake (ACID, time travel) |
| Query engine | PostgreSQL planner | Databricks Photon (vectorised) |
| Namespace | `schema.table` | `catalog.schema.table` (Unity Catalog) |
| Schema evolution | `ALTER TABLE` | `on_schema_change: merge` |
| File optimisation | vacuuming | `OPTIMIZE + ZORDER` (post-hook) |
| Incremental loads | `INSERT ... ON CONFLICT` | Delta `MERGE` |
| Data lineage | none | Unity Catalog auto-lineage |
| Scale | single node | multi-node clusters, PBs of data |

---

## Files

```
dbt_databricks/
├── dbt_project.yml              # Project config (file_format: delta, on_schema_change)
├── profiles.yml.example         # Connection template — copy to ~/.dbt/profiles.yml
└── models/
    ├── staging/
    │   ├── stg_taxi_trips.sql   # Cleaning view (same logic, Databricks SQL syntax)
    │   └── schema.yml           # Source definitions, column tests, descriptions
    └── marts/
        └── fct_trips_daily.sql  # Daily metrics table (extra columns vs Project 1)
```

---

## How to Connect to Databricks

### 1. Install the adapter

```bash
pip install dbt-databricks
```

### 2. Configure your profile

```bash
cp profiles.yml.example ~/.dbt/profiles.yml
# Edit ~/.dbt/profiles.yml with your workspace URL, HTTP path, and catalog
```

### 3. Set your access token

```bash
export DATABRICKS_TOKEN="dapiXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
```

Generate a token in Databricks: **User Settings → Developer → Access tokens**.

### 4. Load source data into Databricks

```sql
-- In Databricks SQL or a notebook:
CREATE CATALOG IF NOT EXISTS main;
CREATE SCHEMA IF NOT EXISTS main.raw;

COPY INTO main.raw.taxi_trips
FROM 's3://your-bucket/nyc-taxi/yellow_tripdata_2024-01.parquet'
FILEFORMAT = PARQUET;
```

### 5. Run dbt

```bash
cd dbt_databricks

# Test the connection
dbt debug

# Run all models
dbt run

# Run tests
dbt test

# Generate and open documentation
dbt docs generate
dbt docs serve
```

---

## Unity Catalog Namespace

dbt-databricks automatically maps the three-level namespace from `profiles.yml`:

```
catalog   →  main            (from profiles.yml: catalog: "main")
schema    →  nyc_taxi_dev    (from profiles.yml: schema: "nyc_taxi_dev")
model     →  stg_taxi_trips  (from model file name)

Full name:   main.nyc_taxi_dev.stg_taxi_trips
```

The `+schema: staging` config in `dbt_project.yml` appends a suffix:

```
main.nyc_taxi_dev_staging.stg_taxi_trips
```

---

## Delta-Specific Features in This Project

### OPTIMIZE + ZORDER (post-hook)
After every full refresh of `fct_trips_daily`, dbt runs:
```sql
OPTIMIZE main.nyc_taxi_dev_marts.fct_trips_daily ZORDER BY (trip_date)
```
This co-locates rows for the same date in the same files, so date-range
queries skip irrelevant data entirely (Delta's data skipping).

### Schema Evolution
`on_schema_change: merge` in `dbt_project.yml` means adding a column to
a model never fails an existing run — Delta merges the new column in.

### Photon
Databricks' vectorised query engine processes dbt-generated SQL automatically.
No code changes needed — Photon is transparent to dbt.
