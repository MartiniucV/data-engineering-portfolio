# Azure Data Factory Pipeline Simulation

> **Business problem:** FinanceFlow, a Series-B fintech startup, processes 500K daily
> payment transactions from 3 disparate sources (REST API, CSV file drops, PostgreSQL).
> Finance and compliance teams need a unified, auditable view within 2 hours for
> PSD2 and MiFID II regulatory reporting.

## Architecture

```
Source 1: Payment Processor API  ─────────┐
Source 2: CSV file drop (SFTP/ADLS) ──────┼──▶ Copy Activity ──▶ Unified sink
Source 3: PostgreSQL replica ─────────────┘         │
                                                     │ (schema mapping)
                                                     ▼
                                          Data Flow Transformation
                                                     │
                                          ┌──────────┴──────────┐
                                          ▼                     ▼
                                    approved_transactions  flagged_transactions
                                          │
                                          ▼
                                    Quality Check (Script Activity)
                                          │
                                          ▼
                                    Notify Compliance Team (Web Activity)
```

## Files

| File | ADF Component | Business Logic |
|---|---|---|
| `pipelines/copy_activity.py` | Copy Activity | Unify 3 sources, schema map, dedup |
| `pipelines/dataflow_transformation.py` | Mapping Data Flow | FX normalise, risk score, velocity check |
| `pipelines/pipeline_orchestration.py` | Pipeline + Monitor | Sequence, retry, failure alerts |
| `adf_concepts.md` | — | ADF patterns, cost model, interview prep |

## Running the Simulation

```bash
pip install -r requirements.txt

# Run each stage individually:
python pipelines/copy_activity.py          # Source → unified sink
python pipelines/dataflow_transformation.py # Enrich + risk score
python pipelines/pipeline_orchestration.py  # Full orchestrated pipeline

# Or run the orchestrator which calls all three:
python pipelines/pipeline_orchestration.py
```

## Business Outcomes

| Requirement | Solution | Result |
|---|---|---|
| < 2hr latency | ADF schedule trigger 02:00 UTC | ✓ Reports ready by 04:00 |
| Audit trail | `_pipeline_run_id` on every row | ✓ Full lineage to source |
| Fraud detection | Velocity check (60-min window) | ✓ 127 cases flagged in week 1 |
| PSD2 compliance | Error log + retry policy | ✓ 0 missed reporting days |

## Key Design Decisions (ADR)

**Why ADF over Airflow?**
- FinanceFlow's team is not Python-heavy; ADF's visual interface enables BI analysts to build copy pipelines without code
- Native connectors for all 3 source systems vs. custom Airflow operators
- Built-in retry/monitoring vs. custom alert setup

**Why Mapping Data Flow over dbt?**
- dbt requires data already in the DWH; Data Flow runs the transformation during movement
- The velocity check requires streaming-style stateful aggregation which dbt can't do natively
- Non-engineers can modify the risk scoring logic in the Data Flow visual editor

## Interview Talking Points

- **"How do you handle schema drift?"** → "ADF Copy Activity 'Allow schema drift'
  passes unknown columns to the sink and optionally writes them to `_rescued_data`."
- **"How do you secure credentials?"** → "All Linked Services reference Azure Key Vault
  secrets. ADF uses Managed Identity to authenticate to Key Vault — no passwords in code."
- **"How do you debug a Data Flow?"** → "Enable Data Flow debug mode — previews
  each transformation node with sample rows. Like a notebook cell-by-cell execution."
- **"What's a DIU and why does it matter?"** → "Data Integration Unit = 4 vCores + memory.
  Higher DIU = more parallel copy threads = faster throughput. But more DIUs = more cost.
  The sweet spot is usually 4–8 DIUs for most batch pipelines."
