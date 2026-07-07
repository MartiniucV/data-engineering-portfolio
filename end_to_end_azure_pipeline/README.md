# End-to-End Azure Data Pipeline — SmartCity Environmental Analytics

> **Business problem:** A European city council deploys 50 environmental monitoring
> stations tracking air quality and weather. They need: EU threshold alerts within 4
> hours, a public health dashboard by 09:00 UTC, and 5-year trend data for urban
> planning. Budget: < $500/month for the complete platform.

## Architecture

```
Open-Meteo API (8 stations, 30 days)
        │  ingestion/api_ingest.py
        ▼
data/smartcity/raw/
        │  processing/spark_transform.py (PySpark-style)
        ▼
data/smartcity/silver/          data/smartcity/gold/
        │  storage/delta_storage.py
        ▼
Delta tables (ADLS Gen2 simulation)
        │  orchestration/pipeline_dag.py (Airflow DAG)
        │  monitoring/data_quality.py (Great Expectations)
        ▼
Streamlit Dashboard (visualization/streamlit_dashboard.py)
```

## Files

| Layer | File | Azure Equivalent |
|---|---|---|
| Ingestion | `ingestion/api_ingest.py` | Azure Function (Timer) |
| Processing | `processing/spark_transform.py` | Databricks Jobs (PySpark) |
| Storage | `storage/delta_storage.py` | ADLS Gen2 + Delta Lake lifecycle |
| Orchestration | `orchestration/pipeline_dag.py` | Azure Managed Airflow / Databricks Workflows |
| Monitoring | `monitoring/data_quality.py` | Great Expectations + Azure Monitor |
| Serving | `visualization/streamlit_dashboard.py` | Azure Container Apps |
| Docs | `architecture.md` | Full Azure production diagram + cost model |

## Quick Start

```bash
pip install -r requirements.txt

# Option 1: Run the full pipeline via Airflow standalone runner
python orchestration/pipeline_dag.py

# Option 2: Run each stage manually
python ingestion/api_ingest.py
python processing/spark_transform.py
python storage/delta_storage.py
python monitoring/data_quality.py
streamlit run visualization/streamlit_dashboard.py
```

## What Makes This Interview-Ready

### Grounded in a Real Regulatory Constraint
The scenario is fictional (SmartCity), but the alerting threshold isn't — it's
built against EU Directive 2008/50/EC's air-quality limits, not an arbitrary
schema. The $188/month cost estimate is a line-by-line calculation from current
Azure UK South pricing (see `architecture.md`), not a rounded guess.

### Azure Service Mapping
Every single function, class, and variable has a comment explaining what Azure
service it maps to and why that service was chosen over alternatives.

### Architecture Decision Records
`architecture.md` documents: why Azure Functions beat ADF for ingestion,
why Event Grid trigger beats schedule trigger, why Container Apps beats App Service.

### Data Quality as a First-Class Citizen
15 Great Expectations-style checks with pass rates, freshness validation,
and EU threshold monitoring. Quality results exported as JSON for Azure Monitor.

### Cost Optimisation
Delta storage lifecycle policy moves old Bronze files to Cool/Archive tiers.
Scale-to-zero on Container Apps. Serverless Azure Functions. Total: ~$188/month.

## Engineering Discussion

- **"Walk me through the pipeline"** → 8 stations → API ingest → Parquet → PySpark clean
  → Delta Gold tables → 15 quality checks → Streamlit dashboard. SLA: 3 hours start-to-finish.
- **"How do you handle EU threshold breaches?"** → "The `exceeds_eu_threshold` column
  flags station-days where AQI > 100. The quality check alerts if exceedances spike.
  In production, Azure Monitor fires a webhook to the city's emergency operations system."
- **"How would you scale this to 500 stations?"** → "The only change is Databricks
  cluster size (+2 workers, ~$60/month). ADLS storage and Functions scale automatically.
  The DAG is parameterised — stations are config, not hardcoded."
- **"What's your SLA if the Open-Meteo API is down?"** → "The Airflow task retries
  3× with exponential backoff (5s, 10s, 20s). If still failing, the on-failure
  callback sends a PagerDuty alert to the on-call engineer. Stale data is kept
  from the previous successful run with a freshness flag on the dashboard."
