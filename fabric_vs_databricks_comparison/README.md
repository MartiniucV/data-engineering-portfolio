# Fabric vs. Databricks Comparison

> **Business problem:** RetailBank is evaluating Microsoft Fabric vs. Databricks
> for a new data platform that will process 10M daily credit card transactions.
> This project implements the SAME pipeline in both styles so the trade-offs
> are visible in code, not just in marketing documents.

## The Experiment

Same dataset, same business logic, two implementations:

| | `fabric_approach.py` | `databricks_approach.py` |
|---|---|---|
| Query engine | DuckDB (mirrors Fabric T-SQL) | pandas (mirrors PySpark) |
| Table format | Parquet (via DuckDB) | `DeltaTableSimulator` (Delta semantics) |
| Write mode | TRUNCATE + INSERT | MERGE (incremental upsert) |
| Schema evolution | SQL `ALTER TABLE` | `mergeSchema=true` |
| BI layer | DirectLake (T-SQL endpoint) | Databricks SQL Warehouse |
| Primary user | SQL analysts | Data engineers / scientists |

## Files

| File | Purpose |
|---|---|
| `fabric_approach.py` | Fabric-style T-SQL pipeline on 50K transactions |
| `databricks_approach.py` | Databricks-style Delta MERGE pipeline, same data |
| `comparison_notebook.ipynb` | Side-by-side in Jupyter with timing and output diff |
| `decision_framework.md` | When to choose each platform + ADR template |

## Quick Start

```bash
pip install -r requirements.txt

python fabric_approach.py       # Fabric style
python databricks_approach.py   # Databricks style
jupyter lab comparison_notebook.ipynb
```

## Key Findings

### Fabric wins for:
- **Power BI users**: DirectLake eliminates the import/refresh cycle entirely
- **SQL-first teams**: every Delta table exposed as T-SQL view automatically
- **Cost predictability**: flat F64 capacity vs variable DBU consumption
- **Operational simplicity**: no cluster management, no DBU tuning

### Databricks wins for:
- **Incremental updates**: Delta MERGE handles late data without full rewrites
- **ML integration**: MLflow, Feature Store, AutoML live next to the ETL code
- **Fine-grained governance**: column-level masking + row filters per Unity Catalog policy
- **Streaming**: Delta Live Tables > Fabric Eventstream for complex event processing

### Surprising finding:
For the RetailBank scenario (batch ETL + BI, no ML), **Fabric F64 is 30% cheaper
and requires less engineering effort**. The Databricks approach is the right choice
only when ML workloads, complex streaming, or multi-cloud requirements exist.

## Architecture Discussion

- **"Can they co-exist?"** → "Yes. Databricks reads from OneLake via ABFSS connector.
  Fabric Shortcuts expose Databricks-written Delta tables. Many enterprises use both:
  Fabric for BI + ADF for simple ETL; Databricks for ML + complex streaming."
- **"Which would you recommend for us?"** → "Depends on three questions: (1) Do you
  have ML/AI workloads today or in the next 2 years? (2) Is your team Python-first or
  SQL-first? (3) Are you Microsoft-centric already? See `decision_framework.md` for
  the structured decision tree."
- **"What's the biggest architectural difference?"** → "Compute model. Fabric CU is
  shared — all workloads (ETL, SQL, notebooks) share the same capacity pool.
  Databricks DBU is per-cluster — each job scales independently. Fabric is better
  for predictable mixed workloads; Databricks is better for bursty, parallel jobs."
