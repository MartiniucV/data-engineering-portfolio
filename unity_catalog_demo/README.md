# Unity Catalog Demo

A hands-on demonstration of **Databricks Unity Catalog** concepts — the
three-level namespace, data governance (row-level security, column masking),
and automatic column-level data lineage — using PySpark + Delta Lake locally.

Everything that runs locally maps directly to a real Databricks workspace.
The README explains each concept and shows the equivalent Databricks SQL.

---

## What is Unity Catalog?

Unity Catalog (UC) is Databricks' unified governance layer for all data and
AI assets. It provides:

| Capability | Description |
|-----------|-------------|
| Three-level namespace | `catalog.schema.table` — one governance layer for all workspaces |
| Fine-grained access control | Table, row, and column-level permissions |
| Data lineage | Automatic column-level lineage captured on every read/write |
| Data discovery | Searchable metadata, tags, and business descriptions |
| Delta Sharing | Open-protocol sharing across organisations without copying data |
| Audit logging | Every data access event stored in `system.access.audit` |

---

## Architecture

```
                Unity Catalog
                ┌─────────────────────────────────────────────────────┐
                │                                                     │
                │   catalog: portfolio                                │
                │   │                                                 │
                │   ├── schema: bronze                                │
                │   │    └── table: raw_weather         (Delta)       │
                │   │                                                 │
                │   ├── schema: silver                                │
                │   │    └── table: clean_weather       (Delta)       │
                │   │                   ↑ Row Filter                  │
                │   │                   ↑ Column Mask                 │
                │   │                                                 │
                │   ├── schema: gold                                  │
                │   │    └── table: weather_daily       (Delta)       │
                │   │                                                 │
                │   └── schema: analytics                             │
                │        └── table: weather_report      (Delta)       │
                │                                                     │
                └─────────────────────────────────────────────────────┘

                Lineage (captured automatically):
                Open-Meteo API → raw_weather → clean_weather → weather_daily
```

---

## Files

| File | Demonstrates |
|------|-------------|
| `setup_catalog.py` | Three-level namespace, Bronze/Silver/Gold population |
| `governance.py` | Row-level security, column masking, data tagging |
| `lineage.py` | Column-level lineage graph and impact analysis |
| `requirements.txt` | Python dependencies |

---

## Concepts Demonstrated

### 1. Three-Level Namespace (`setup_catalog.py`)

Unity Catalog introduces a catalog level above the traditional schema level:

```sql
-- Real Databricks SQL
CREATE CATALOG  IF NOT EXISTS portfolio;
CREATE SCHEMA   IF NOT EXISTS portfolio.bronze;
CREATE TABLE    portfolio.bronze.raw_weather (
    date             DATE,
    city             STRING,
    temperature_max  DOUBLE,
    ...
) USING DELTA;
```

Locally simulated as Delta tables under `delta/portfolio/{schema}/`.

### 2. Row-Level Security (`governance.py`)

A Row Access Policy is a SQL function that returns TRUE/FALSE per row based
on the current user's group membership:

```sql
-- Real Databricks SQL
CREATE ROW ACCESS POLICY region_policy
AS (city STRING) RETURNS BOOLEAN
RETURN CASE
  WHEN is_member('admins')      THEN TRUE
  WHEN is_member('eu_analysts') THEN city IN ('London')
  WHEN is_member('us_analysts') THEN city IN ('New York', 'Sydney')
  ELSE FALSE
END;

ALTER TABLE portfolio.silver.clean_weather
SET ROW FILTER region_policy ON (city);
```

The filter is invisible to users and enforced on every query automatically.

### 3. Column Masking (`governance.py`)

A Column Mask obfuscates sensitive column values for non-privileged users:

```sql
-- Real Databricks SQL
CREATE COLUMN MASK wind_mask
AS (col DOUBLE) RETURNS DOUBLE
RETURN CASE WHEN is_member('admins') THEN col ELSE -1.0 END;

ALTER TABLE portfolio.silver.clean_weather
ALTER COLUMN wind_speed_kmh SET MASK wind_mask;
```

### 4. Data Tagging (`governance.py`)

Tags classify columns for compliance reporting:

```sql
ALTER TABLE portfolio.silver.clean_weather
ALTER COLUMN city SET TAGS ('pii' = 'false', 'classification' = 'internal');
```

Query tagged columns via system tables:
```sql
SELECT * FROM system.information_schema.column_tags
WHERE tag_name = 'classification' AND tag_value = 'confidential';
```

### 5. Column-Level Lineage (`lineage.py`)

On Databricks, lineage is captured automatically. Query it via:

```sql
SELECT source_table_name, source_column_name,
       target_table_name, target_column_name
FROM system.access.column_lineage
WHERE target_table_name = 'weather_daily';
```

Locally we manually declare the same lineage graph to illustrate the structure.

---

## Prerequisites

- Python 3.10+, Java 11+
- `governance.py` and `lineage.py` run with pandas only (no Spark needed)

## Quick Start

```bash
pip install -r requirements.txt

# 1. Create catalog structure and populate all layers
python setup_catalog.py

# 2. Demo row-level security and column masking (pandas only, no Spark)
python governance.py

# 3. Demo column-level lineage graph
python lineage.py
```

## On Real Databricks

The `setup_catalog.py` equivalent in Databricks:

```python
# In a Databricks notebook
spark.sql("CREATE CATALOG IF NOT EXISTS portfolio")
spark.sql("CREATE SCHEMA IF NOT EXISTS portfolio.bronze")
spark.sql("CREATE SCHEMA IF NOT EXISTS portfolio.silver")
spark.sql("CREATE SCHEMA IF NOT EXISTS portfolio.gold")

df.write.format("delta").saveAsTable("portfolio.bronze.raw_weather")
```

Governance is configured in the **Catalog Explorer** UI or via SQL — no code
changes to your data pipelines needed.
