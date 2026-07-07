# Azure Data Factory — Concepts & Local Code Mapping

## Pipeline Component Mapping

| Local Code | ADF Component | Description |
|---|---|---|
| `copy_activity.py` | **Copy Activity** | Move data between 90+ source/sink connectors |
| `dataflow_transformation.py` | **Mapping Data Flow** | Code-free Spark-based transformations |
| `pipeline_orchestration.py` | **Pipeline** | Orchestrate activities with dependencies |
| `RetryPolicy` class | Policy → `retry`, `retryIntervalInSeconds` | Per-activity retry configuration |
| `ActivityRunMetrics` | Monitor → Activity Runs | Duration, rows read/written, throughput |
| `on_failure_callback` | **Web Activity** → Logic App | Notifications and alerting |

## ADF Architecture

```
ADF Studio (visual authoring)
│
├── Linked Services        ← connection strings, credentials (→ Key Vault)
├── Datasets               ← schema definitions for sources and sinks
├── Pipelines              ← activity graphs with dependencies
│   ├── Copy Activity
│   ├── Mapping Data Flow
│   ├── Script Activity    (run SQL against Azure SQL / Synapse)
│   ├── Web Activity       (call REST endpoint / Logic App)
│   ├── Execute Pipeline   (nested pipelines)
│   └── Lookup Activity    (read reference data)
├── Triggers               ← Schedule, Storage Event, Tumbling Window, Manual
└── Integration Runtime    ← Azure IR (cloud), Self-hosted IR (on-premises)
```

## Copy Activity: Key Features

### Parallel Copy
ADF can use multiple threads to read a source in parallel:
```json
"parallelCopies": 4,
"dataIntegrationUnits": 8
```
Throughput: up to 4 GB/min from ADLS Gen2 → ADLS Gen2.

### Staged Copy
For sources that don't support parallel reads, use Azure Blob as a staging area:
```json
"enableStaging": true,
"stagingSettings": {"linkedServiceName": {"referenceName": "AzureBlobStorage"}}
```

### Fault Tolerance
```json
"faultTolerance": {
    "skipIncompatibleRow": true,
    "redirectIncompatibleRowSettings": {
        "linkedServiceName": {"referenceName": "ErrorLogStorage"},
        "path": "error-logs/incompatible-rows/"
    }
}
```

## Mapping Data Flow: Key Transformations

| Transformation | Local equivalent | Use case |
|---|---|---|
| Source | `pd.read_csv()` / `pd.read_parquet()` | Read input data |
| Derived Column | `df["new_col"] = expr` | Add/modify columns |
| Filter | `df[mask]` | Remove rows |
| Lookup | `df.merge(ref_df)` | Join to reference table |
| Aggregate | `df.groupby().agg()` | Group and aggregate |
| Window | `df.rolling()` / `df.expanding()` | Rolling calculations |
| Conditional Split | `df[mask], df[~mask]` | Branch into multiple streams |
| Flatten | `df.explode()` | Unnest arrays/structs |
| Sink | `df.to_parquet()` | Write output |

## Triggers

| Trigger Type | Use Case | Local equivalent |
|---|---|---|
| Schedule | Daily at 02:00 UTC | cron job |
| Storage Event | Run when new blob arrives in ADLS | inotifywait / Azure Event Grid |
| Tumbling Window | Process hourly windows with backfill | Airflow `schedule_interval` |
| Manual | Ad-hoc runs | direct Python call |

## Cost Model

| Component | Pricing (approximate) |
|---|---|
| Orchestration (pipeline runs) | $1 per 1,000 activity runs |
| Copy Activity | $0.25 per 1,000 DIU-hours |
| Mapping Data Flow | $0.30 per vCore-hour (Spark compute) |
| Self-hosted IR | $0.10 per vCore-hour |

**FinanceFlow estimate:** 500K transactions/day, 3 sources, daily pipeline:
- 3 Copy Activities + 1 Data Flow + 1 Script = ~5 activities/run
- Monthly: 5 × 30 = 150 activities → **$0.15/month orchestration**
- Data Flow (1-hour Spark cluster, 8 vCores): **$2.40/month**
- **Total: ~$3/month** for the ETL pipeline

## Key Engineering Decisions

1. **"What's the difference between Copy Activity and Data Flow?"**
   Copy Activity = data movement (optimised for throughput, no Spark).
   Data Flow = data transformation (runs on Spark, supports complex joins/aggregations).
   Rule of thumb: if you need to transform shape, use Data Flow; if you just need
   to move data, Copy Activity is faster and cheaper.

2. **"How do you handle secrets in ADF?"**
   Linked Services reference Azure Key Vault secrets by name.
   ADF uses its Managed Identity to authenticate to Key Vault.
   No credentials ever stored in ADF JSON definitions.

3. **"What's a Self-hosted Integration Runtime?"**
   An agent installed on an on-premises VM or VNet-connected machine.
   Allows ADF to reach data sources that aren't publicly accessible
   (on-prem SQL Server, private ADLS, internal APIs).

4. **"How would you handle late-arriving data in ADF?"**
   Tumbling Window trigger with a dependency on itself (self-dependency).
   Each window waits for all data within the window to arrive before processing.
   Combine with a watermark column to detect and re-process late records.
