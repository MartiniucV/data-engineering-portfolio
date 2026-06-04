# SmartCity Environmental Analytics — Azure Production Architecture

## Business Context
A European city (pop. 500K) deploys 50 environmental monitoring stations tracking
air quality proxies and weather conditions. Requirements:
- EU Directive 2008/50/EC: alert when AQI > 100 within 4 hours
- Public health dashboard: daily report by 09:00 UTC
- Urban planning: 5-year trend analysis for infrastructure decisions
- SLA: pipeline completes by 06:00 UTC daily (3 hours after ingestion)

## Production Azure Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    INGESTION LAYER                                      │
│                                                                         │
│  50 Monitoring Stations                                                 │
│       │ sensor readings                                                 │
│       ▼                                                                 │
│  Azure API Management  ──── rate limiting (1000 req/hr) ───►           │
│       │                     auth (API key in Key Vault)                 │
│       ▼                                                                 │
│  Azure Function (Timer: "0 * * * *")  ◄── ingestion/api_ingest.py      │
│       │ parquet files                                                   │
│       ▼                                                                 │
│  ADLS Gen2 (raw container)                                              │
│  smartcity/{station_id}/{yyyy/mm/dd}/readings_{ts}.parquet             │
└───────────────────────────────────────────────────────────────────────┬─┘
                                                                        │
                              Azure Event Grid (blob-created event)    │
                                                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    PROCESSING LAYER                                     │
│                                                                         │
│  Databricks Workflows (Job: "smartcity_etl")  ◄── event trigger        │
│       │                                                                 │
│       ├── Task 1: spark_transform (processing/spark_transform.py)      │
│       │    ├── Input:  ADLS Gen2 raw/                                  │
│       │    ├── Silver: partitioned by station_id + ingest_date         │
│       │    └── Gold:   daily_station_metrics, zone_weekly_metrics      │
│       │                                                                 │
│       └── Task 2: delta_storage (storage/delta_storage.py)            │
│            └── ADLS Gen2 analytics/ container (Delta tables)           │
└───────────────────────────────────────────────────────────────────────┬─┘
                                                                        │
┌─────────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION LAYER                                  │
│                                                                         │
│  Azure Managed Airflow (or Databricks Workflows DAG)                   │
│  orchestration/pipeline_dag.py                                          │
│                                                                         │
│  Schedule: 03:00 UTC daily  |  SLA: 06:00 UTC                         │
│                                                                         │
│  ingest ──► transform ──► store_delta ──► quality_check               │
│                                              │                          │
│                                         ┌───┴────┐                     │
│                                         │        │                      │
│                                    success   failure                    │
│                                         │        │                      │
│                                    Teams✓   PagerDuty⚠                │
└───────────────────────────────────────────────────────────────────────┬─┘
                                                                        │
┌─────────────────────────────────────────────────────────────────────────┐
│                    QUALITY LAYER                                        │
│                                                                         │
│  Great Expectations (monitoring/data_quality.py)                       │
│       │ 6 expectation suites, 15 checks                                │
│       │ Results → ADLS Gen2 quality-results/                          │
│       │ Azure Monitor custom metric: quality_pass_rate                 │
│       └── Alert if pass_rate < 95% → Teams notification               │
│                                                                         │
└───────────────────────────────────────────────────────────────────────┬─┘
                                                                        │
┌─────────────────────────────────────────────────────────────────────────┐
│                    SERVING LAYER                                        │
│                                                                         │
│  Azure Container Apps (auto-scale, scale-to-zero)                      │
│  visualization/streamlit_dashboard.py                                   │
│       │                                                                 │
│       ├── Reads from ADLS Gen2 analytics/ via Managed Identity         │
│       ├── Azure Front Door: CDN + SSL termination                      │
│       ├── Azure AD B2C: optional public/authenticated mode             │
│       └── Cache TTL: 15 minutes (balances freshness vs DB load)        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Component → Azure Service Mapping

| `local file` | Azure Production Service | Why This Choice |
|---|---|---|
| `ingestion/api_ingest.py` | Azure Function (Timer trigger) | Serverless, scales to zero, $0.20/1M executions |
| `processing/spark_transform.py` | Databricks Jobs (PySpark) | Photon engine, Delta MERGE, auto-scaling |
| `storage/delta_storage.py` | ADLS Gen2 + Delta Lake | ADLS = cheapest Azure storage, Delta = ACID |
| `orchestration/pipeline_dag.py` | Azure Managed Airflow / Databricks Workflows | Complex dependencies, retry, SLA monitoring |
| `monitoring/data_quality.py` | Great Expectations + Azure Monitor | Industry standard QE framework |
| `visualization/streamlit_dashboard.py` | Azure Container Apps | Minimal ops, auto-scale, cost-efficient |

## Cost Estimate (monthly, Azure UK South)

| Service | Config | Cost/month |
|---|---|---|
| Azure Functions | 1M executions/month (8 stations × 30 days × 48 runs) | $0.20 |
| ADLS Gen2 | 100 GB data (Hot tier) | $2.00 |
| Databricks Jobs | Standard_DS3_v2, 2 DBU/hr, 1 hr/day | $30 |
| Azure Managed Airflow | Smallest SKU, 1 scheduler | $150 |
| Container Apps | 0.5 vCPU, 1 GB RAM, scale-to-zero | $5 |
| Azure Monitor | Basic alerts | $1 |
| **Total** | | **~$188/month** |

## Scalability Notes

Current: 8 stations × 30 days × 30 metrics = 7,200 rows/run
Target (50 stations): 45,000 rows/run — same architecture, no changes needed

At 500 stations (city cluster network):
- Databricks cluster: add 2 more workers ($60/month extra)
- ADLS Gen2: cost grows linearly with storage
- Dashboard: Container Apps autoscales on CPU

## Lessons Learned

1. **Azure Functions for ingestion beats ADF HTTP connector** — Functions have full
   Python control (custom retry, structured logging, Application Insights integration)
   at 1/10th the ADF copy activity cost.

2. **Event Grid trigger beats schedule trigger** — Processing starts seconds after
   ingestion completes rather than waiting for the next scheduled slot.

3. **Container Apps > App Service for Streamlit** — Scale-to-zero means $0 cost
   overnight when the dashboard has no visitors.

4. **Great Expectations suite versioning** — Storing `suite_v1`, `suite_v2` lets you
   compare quality scores across pipeline changes in Azure Monitor dashboards.
