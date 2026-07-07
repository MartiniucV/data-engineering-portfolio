# Databricks + Azure Integration — Concepts & Patterns

## Service Mapping

| Pattern | Real Azure Service | Local Simulation |
|---|---|---|
| Raw data storage | ADLS Gen2 | `data/adls_simulation/` filesystem |
| Mount point | `dbutils.fs.mount(...)` | `StorageMount.path()` abstraction |
| Authentication | Managed Identity / Service Principal | Environment variables |
| Secrets | Azure Key Vault + Databricks Secret Scope | `os.environ.get()` |
| New file detection | Azure Event Grid + AutoLoader `cloudFiles` | Directory scan + JSON checkpoint |
| Streaming ingest | Azure IoT Hub → ADLS Gen2 → AutoLoader | File watcher simulation |
| Quality gating | Delta Live Tables `@expect_or_quarantine` | `DLTPipeline` class |
| Alerting | Azure Monitor + Action Groups | Log output |

## ADLS Gen2 Authentication Patterns

### Managed Identity (recommended for production)
```python
# In Databricks cluster config:
# spark.hadoop.fs.azure.account.auth.type.{account}.dfs.core.windows.net OAuth
# spark.hadoop.fs.azure.account.oauth.provider.type... MsiTokenProvider
# No credentials in code — cluster's Managed Identity has Storage Blob Data Contributor

df = spark.read.parquet(f"abfss://raw@{account}.dfs.core.windows.net/sensor-data/")
```

### Unity Catalog External Location (modern approach)
```sql
-- Grant once in Unity Catalog (admin task):
CREATE EXTERNAL LOCATION raw_data_location
URL 'abfss://raw@manufacturex.dfs.core.windows.net/'
WITH (STORAGE CREDENTIAL manufacturex_mi);

-- Developers use it transparently:
CREATE TABLE bronze.sensor_readings
LOCATION 'abfss://raw@manufacturex.dfs.core.windows.net/sensor-data/';
```

### Legacy Mount Points (still common pre-UC workspaces)
```python
dbutils.fs.mount(
    source="abfss://sensor-data@manufacturex.dfs.core.windows.net/",
    mount_point="/mnt/sensor-data",
    extra_configs={
        "fs.azure.account.auth.type": "OAuth",
        "fs.azure.account.oauth.provider.type":
            "org.apache.hadoop.fs.azurebfs.oauth2.ClientCredsTokenProvider",
        "fs.azure.account.oauth2.client.id":
            dbutils.secrets.get(scope="kv-scope", key="sp-client-id"),
        "fs.azure.account.oauth2.client.secret":
            dbutils.secrets.get(scope="kv-scope", key="sp-client-secret"),
        "fs.azure.account.oauth2.client.endpoint":
            f"https://login.microsoftonline.com/{tenant_id}/oauth2/token",
    }
)
```

## AutoLoader vs. Trigger-Once Read

| | `spark.read.parquet(path)` | AutoLoader (`cloudFiles`) |
|---|---|---|
| Processes new files only | ✗ (reads all) | ✓ (checkpoint-based) |
| Schema inference | manual | automatic |
| Schema evolution | fail on new column | `_rescued_data` column |
| Scales to millions of files | slow (glob scan) | fast (file notification) |
| Exactly-once | ✗ | ✓ |

**When to use AutoLoader:**
- Landing zone receives new files continuously
- Number of files > 10,000 (glob scan becomes expensive)
- Need restart-safe incremental processing

## Delta Live Tables vs. Structured Streaming

| | Structured Streaming | Delta Live Tables |
|---|---|---|
| Checkpointing | manual (`checkpointLocation`) | automatic |
| Quality checks | custom validation code | `@expect` decorators |
| Lineage | none | automatic in Unity Catalog |
| Monitoring | Spark UI | DLT Pipeline UI + event_log table |
| Deployment | Databricks Job | DLT Pipeline (separate resource) |
| Cost | cluster hours | pipeline hours (often cheaper) |

**Recommendation:** Use DLT for new streaming pipelines. Use Structured Streaming
only when you need features DLT doesn't support (e.g., `foreachBatch`).

## ManufactureX Architecture in Real Azure

```
10,000 IoT Sensors
      │
      │ MQTT / AMQP
      ▼
Azure IoT Hub  ─────── Device Twin (config management)
      │
      │ Message Routing
      ▼
ADLS Gen2 (raw/)  ← parquet files, ~5min batches
      │
      │ AutoLoader cloudFiles
      ▼
Databricks DLT Pipeline
  ├── bronze_raw_sensors        (@dlt.table, streaming)
  ├── silver_validated          (@dlt.expect_or_quarantine)
  └── gold_plant_health_hourly  (@dlt.table, aggregate)
      │
      │ Delta table in Unity Catalog
      ▼
Power BI Embedded  →  Plant Operations Dashboard
      │
Azure Monitor Alerts  →  Teams / PagerDuty on anomaly
```

## Cost Estimate (ManufactureX, Azure UK South)

| Component | Config | Monthly cost |
|---|---|---|
| Azure IoT Hub | S1 tier, 10K devices, 400K msgs/day | $80 |
| ADLS Gen2 storage | 10 TB (1 year of raw data) | $200 |
| Databricks DLT | 1 cluster, 4 DBUs/hr, 24/7 | $2,880 |
| Power BI Premium | 10 users | $100 |
| **Total** | | **~$3,260/month** |

At ManufactureX's scale, the $180K plant shutdown that triggered this
project pays for **55 months** of this pipeline.

## Architecture Discussion

1. **"What's the difference between a mount and an External Location?"**
   Mounts are workspace-scoped and not governed by Unity Catalog — any user on
   the cluster can access the mount. External Locations are UC-governed with
   table/column-level GRANT permissions. Mounts are deprecated in favour of UC.

2. **"How does AutoLoader handle schema evolution?"**
   New columns → rescued into `_rescued_data` JSON column (no pipeline failure).
   Type changes → configurable: `failOnDataLoss` or rescue.
   Schema evolution log stored in `checkpointLocation/_schemas/`.

3. **"What happens if a DLT pipeline fails halfway through?"**
   DLT resumes from the last successful checkpoint. Delta's ACID guarantees mean
   partially-written tables are invisible to readers. The pipeline retries the
   failed table without re-processing already-committed tables.

4. **"How do you optimise a DLT pipeline for cost?"**
   Use `enhanced_autoscaling: true` — cluster scales to 1 node during idle periods.
   Set `pipelines.trigger.interval: "1 hour"` for low-frequency pipelines.
   Use `OPTIMIZE ZORDER` on Gold tables to reduce downstream SQL Warehouse scans.
