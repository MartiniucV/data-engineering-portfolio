# Fabric vs. Databricks Decision Framework

## TL;DR

| Choose **Microsoft Fabric** when... | Choose **Databricks** when... |
|---|---|
| Team is primarily BI-focused (Power BI heavy) | Team is data engineering / ML / data science focused |
| Organisation is Microsoft-heavy (Azure, M365, Teams) | Multi-cloud or AWS/GCP workloads |
| Low-code / no-code tools are a priority | Code-first, Python/Spark is the standard |
| Consolidating BI + ETL under one platform | Advanced ML/AI pipelines (MLflow, Feature Store) |
| Budget is CU-based and predictable | Pay-as-you-go, burst workloads |
| SQL analysts outnumber Python engineers | Python engineers outnumber SQL analysts |

## Head-to-Head Comparison

### Architecture

```
Microsoft Fabric                    Databricks on Azure
──────────────────────              ──────────────────────────────
OneLake (ADLS Gen2)                 ADLS Gen2 (you manage)
Lakehouse (Delta)                   Delta Lake (you configure)
SQL Analytics Endpoint              Databricks SQL Warehouse
Power BI DirectLake                 Power BI + Databricks connector
Fabric Pipelines (ADF-like)         Databricks Workflows
Fabric Notebooks (PySpark/pandas)   Databricks Notebooks
Eventstream (Event Hubs)            Spark Structured Streaming
Real-time Analytics (KQL)           Structured Streaming + Delta
```

### For RetailBank (the scenario in this project)

**Fabric wins if:**
- 200 analysts are primarily Power BI users
- Most workloads are scheduled batch SQL
- Already on Microsoft 365 E5 (Fabric included in some tiers)
- No ML model training requirements
- IT team prefers managed service (less operational overhead)

**Databricks wins if:**
- Building fraud detection ML models alongside the ETL
- Need column-level access control enforced at query time (Unity Catalog)
- Require MERGE with complex conditions (Delta MERGE is more powerful than Fabric's)
- Multi-workspace isolation needed per regulatory domain
- Data science team already uses Python/Spark

### Governance Comparison

| Feature | Fabric | Databricks |
|---|---|---|
| Table permissions | Workspace + SQL GRANT | Unity Catalog GRANT |
| Column-level security | Column masking (SQL) | Column masking (UC) |
| Row-level security | Row filter (SQL) | Row filter (UC) |
| Data lineage | Workspace lineage (basic) | Column-level auto-lineage |
| Data classification tags | MS Purview labels | UC custom tags |
| Cross-workspace sharing | Shortcuts, Mirroring | Delta Sharing |
| Audit logging | MS Purview + Fabric Activity | system.access.audit |

### Performance at Scale

| Workload | Fabric | Databricks |
|---|---|---|
| Power BI on 1B rows | ⭐⭐⭐⭐⭐ (DirectLake) | ⭐⭐⭐ (connector import) |
| Batch ETL, 10 TB/day | ⭐⭐⭐ (Spark, shared CU) | ⭐⭐⭐⭐⭐ (Photon + DBUs) |
| ML model training | ⭐⭐ (Spark ML, limited) | ⭐⭐⭐⭐⭐ (MLflow + GPU clusters) |
| Real-time streaming | ⭐⭐⭐ (Eventstream + KQL) | ⭐⭐⭐⭐⭐ (DLT + Structured Streaming) |
| Ad-hoc SQL | ⭐⭐⭐⭐ (SQL Warehouse) | ⭐⭐⭐⭐⭐ (Serverless SQL Warehouse) |

### Cost Modelling (RetailBank: 10M tx/day)

**Fabric F64 (monthly):**
- Capacity: $4,000/month flat
- Storage: ~$200 (ADLS Gen2)
- Power BI Premium: included
- **Total: ~$4,200/month, unlimited users**

**Databricks (monthly):**
- Jobs compute: 3 clusters × 8 DBUs/hr × 8 hrs/day × 30 = 5,760 DBUs → ~$2,880
- SQL Warehouse (serverless): auto-pause → ~$200 active hours → $1,000
- ADLS Gen2: $200
- Power BI Pro: 200 users × $10 = $2,000
- **Total: ~$6,080/month**

**Conclusion for RetailBank:** Fabric is ~30% cheaper AND simpler for a
BI-centric organisation. If ML workloads are added later, consider
a hybrid: Fabric for BI + Databricks ML cluster connected to the same OneLake.

## Hybrid Architecture: The Best of Both

```
                    OneLake / ADLS Gen2
                    ┌────────────────────┐
                    │                    │
          ┌─────────┴──────┐   ┌─────────┴────────┐
          │  Microsoft      │   │  Databricks       │
          │  Fabric         │   │  (ML / Eng)       │
          │                 │   │                   │
          │  Lakehouse      │   │  Unity Catalog     │
          │  SQL Warehouse  │   │  MLflow           │
          │  Power BI       │   │  Feature Store    │
          │  Pipelines      │   │  DLT              │
          └─────────────────┘   └───────────────────┘
```

Databricks can read/write directly to OneLake using the ABFSS connector.
Fabric can expose Databricks-written Delta tables as Shortcuts.

## ADR (Architectural Decision Record)

**Decision:** Choose Databricks for ManufactureX IoT pipeline (Project 11)
**Date:** 2024-01-15
**Status:** Accepted

**Context:** ManufactureX needs to process 28.8M sensor readings/day from
10,000 factory machines with ML anomaly detection.

**Decision drivers:**
1. ML team already uses Databricks for model training
2. AutoLoader needed for reliable incremental ingestion of 34,560 files/day
3. DLT expectations required for safety-critical data quality gating
4. Unity Catalog column-level lineage needed for GDPR audit trail

**Alternatives considered:**
- Fabric: rejected — no native AutoLoader equivalent; DLT has no Fabric counterpart
- ADF + Synapse: rejected — Python/Spark code complexity harder to maintain in ADF

**Consequences:**
- +: Better ML integration, faster ETL (Photon), more control
- -: Higher cost than Fabric F64 for same workload; more operational expertise needed
