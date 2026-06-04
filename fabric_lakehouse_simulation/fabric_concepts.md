# Microsoft Fabric Concepts — Local Code Mapping

## How Local Code Maps to Real Fabric

| Local Simulation | Real Microsoft Fabric | Notes |
|---|---|---|
| `data/onelake/RetailCo.Lakehouse/` | OneLake (`https://{tenant}.dfs.fabric.microsoft.com/`) | OneLake is ADLS Gen2 behind the scenes |
| `Files/bronze/*.parquet` | Lakehouse **Files section** | Unmanaged storage; no auto-table registration |
| `Tables/silver/`, `Tables/gold/` | Lakehouse **Tables section** | Managed Delta tables; auto-registered in Metastore |
| DuckDB connection | **SQL Analytics Endpoint** | T-SQL read-only access to all Tables/ Delta tables |
| DuckDB SQL queries | **Power BI DirectLake** | Power BI reads Delta files directly — no import |
| `lakehouse.py` functions | **Fabric Notebook** (PySpark or pandas) | Run on Spark clusters within Fabric |
| Batch Python run | **Fabric Data Pipeline** | Low-code ADF-style orchestration built into Fabric |
| Local Parquet files | **Fabric Shortcuts** | Point at ADLS/S3/GCS without copying data |

## OneLake Architecture

```
Microsoft Fabric Workspace
│
├── RetailCo.Lakehouse
│   ├── Files/                    ← Unmanaged (Parquet, CSV, JSON, images)
│   │   └── bronze/
│   │       ├── orders.parquet
│   │       ├── products.parquet
│   │       └── customers.parquet
│   │
│   └── Tables/                   ← Managed Delta tables (auto-registered)
│       ├── silver/
│       │   └── orders/           ← Delta table (_delta_log + .parquet files)
│       └── gold/
│           ├── fct_revenue_daily/
│           └── dim_customer_ltv/
│
├── RetailCo.Warehouse             ← T-SQL DWH (separate from Lakehouse)
├── RetailCo.SemanticModel         ← Power BI model (DirectLake mode)
└── RetailCo.Report                ← Power BI report
```

## Key Fabric Differentiators

### DirectLake Mode (the "wow factor")
Power BI normally imports data (slow, stale) or uses DirectQuery (slow, live).
DirectLake reads Delta Parquet files from OneLake **directly into the VertiPaq
engine** — zero data copy, zero latency for refresh, full compression.

Result: sub-second dashboard response on tables with **billions of rows**.

### Shortcuts
A Shortcut is a pointer to data stored elsewhere without copying it:
- ADLS Gen2 → expose as OneLake table
- S3 → expose as OneLake table
- Another Lakehouse → cross-workspace data sharing

Real use case: RetailCo's supplier sends data to their own S3 bucket.
Create a Shortcut in RetailCo's Lakehouse pointing to that bucket —
data appears as a Delta table immediately, no ETL needed.

### Mirroring (Zero-ETL)
Mirror Azure SQL DB, Cosmos DB, or Snowflake into OneLake:
- Changes replicate within minutes
- No ingestion pipeline code
- Mirrored data becomes a Lakehouse table accessible to Spark, SQL, Power BI

### Capacity (CU) Model
Fabric uses Capacity Units (CUs) — a shared pool across all workloads:
- One F64 capacity = 64 CUs ≈ $4,000/month
- Compute (Spark, SQL Warehouse, Pipelines) consumes CUs
- Storage is billed separately (ADLS Gen2 pricing)
- Smoothing: burst workloads borrow from a 24-hour smoothing window

**When Fabric beats Databricks on cost:**
- Organisation already has Microsoft 365 + Azure → Fabric included in some tiers
- Mostly BI + SQL users (low Spark intensity) → CU model cheaper than per-DBU
- Small team with mixed skills → no-code tools save engineering time

## Interview Talking Points

1. **"Explain OneLake"** → "One logical data lake per Fabric tenant. All Lakehouses,
   Warehouses, and semantic models point to the same physical storage.
   Eliminates data silos — one governance layer, one lineage graph."

2. **"How does DirectLake work?"** → "Fabric stores Delta tables in OneLake (ADLS Gen2).
   Power BI VertiPaq engine reads the Delta Parquet files directly using
   columnar compression. No import job, no DirectQuery overhead.
   Achieves Import-mode speed on live Delta data."

3. **"When would you choose Fabric over Databricks?"** → "See decision_framework.md
   in the fabric_vs_databricks_comparison project."

4. **"What's a Fabric Shortcut?"** → "A zero-copy pointer to external storage.
   When you create a Shortcut to an S3 bucket, Fabric registers it as a table
   in the Metastore but doesn't move any data. Reads go directly to S3."
