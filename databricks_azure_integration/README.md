# Databricks + Azure Integration Patterns

> **Business problem:** ManufactureX, an industrial manufacturer, runs 10,000 factory
> sensors across 12 plants emitting readings every 30 seconds (28.8M records/day).
> A false alarm triggered by bad data caused a $180K plant shutdown.
> The new pipeline adds data quality gating with automatic quarantine.

## Architecture

```
10,000 IoT Sensors (30-sec intervals)
        │
        │ Azure IoT Hub → Message Routing
        ▼
ADLS Gen2 raw/ container
(data/adls_simulation/sensor-data/raw/)
        │
        │ AutoLoader (cloudFiles) — incremental, checkpoint-based
        ▼
Databricks DLT Pipeline
        │
        ├── bronze_raw              (all records)
        │
        ├── silver_validated        (@expect_or_quarantine)
        │   ├── ✓ valid readings    → silver table
        │   └── ✗ invalid readings  → quarantine table
        │
        └── gold_plant_health_hourly (aggregated KPIs)
                │
                ▼
        Power BI Plant Dashboard (via Databricks SQL Warehouse)
        Azure Monitor Alerts (anomaly rate threshold)
```

## Files

| File | Pattern | Business Role |
|---|---|---|
| `mount_adls.py` | ADLS Gen2 Mount / External Location | Storage abstraction, cost model |
| `medallion_with_autoloader.py` | AutoLoader incremental ingestion | Never re-process old files |
| `delta_live_tables_simulation.py` | DLT with expectations + quarantine | Prevent bad data reaching ML models |
| `azure_concepts.md` | Reference guide | Auth patterns, cost estimate, ADRs |

## Quick Start

```bash
pip install -r requirements.txt

# Run in order:
python mount_adls.py                        # Simulate ADLS landing zone + mount patterns
python medallion_with_autoloader.py         # Incremental ingestion with checkpoint
python delta_live_tables_simulation.py      # DLT quality pipeline
```

## Business Impact

| Problem | Solution | Result |
|---|---|---|
| Bad data caused $180K shutdown | DLT `@expect_or_quarantine` | Invalid readings isolated before ML scoring |
| Re-processing all files daily | AutoLoader checkpoint | Only new files processed → 10x faster |
| GDPR audit trail required | Unity Catalog column lineage | Every column's origin tracked automatically |
| No monitoring visibility | DLT event_log + quality metrics | Quality score per pipeline run |

## Data Quality Results (simulated)

From `delta_live_tables_simulation.py` output:
- 5% anomaly rate detected and quarantined
- `valid_temperature_range`: 99.2% pass rate
- `non_null_sensor_id`: 100% pass rate
- Quarantine table provides root cause analysis for operations team

## Scalability Notes

At ManufactureX's full scale (10,000 sensors):
- 28.8M rows/day = ~2 GB compressed Parquet/day
- AutoLoader processes 34,560 files/day in < 10 minutes (vs 4 hours with glob scan)
- DLT enhanced autoscaling: 1–8 nodes, saves ~60% during off-peak hours
- Gold table ZORDER BY (plant_id, hour): 85% reduction in query scan size

## Interview Talking Points

- **"Why AutoLoader over spark.read?"** → "AutoLoader uses file change notifications
  or directory listing to find only NEW files. With 34K files/day after 1 year that's
  12M files — a glob scan would take hours. AutoLoader is O(new files), not O(total)."
- **"What happens when a DLT expectation fails?"** → "Depends on the action.
  `@expect_or_quarantine` routes bad rows to a separate table while the pipeline
  continues. `@expect_or_fail` stops the entire pipeline — used for safety-critical data."
- **"How do you handle IoT schema drift?"** → "AutoLoader's `_rescued_data` column
  captures any new fields added by firmware updates. The pipeline doesn't break;
  we review the rescued data and add the new column to the schema when ready."
- **"Unity Catalog vs legacy mounts?"** → "Mounts are workspace-scoped — any user on
  any cluster can read them. UC External Locations are governed by GRANT statements,
  audited in `system.access.audit`, and support column-level lineage."
