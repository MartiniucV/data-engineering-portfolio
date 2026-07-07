# Microsoft Fabric Lakehouse Simulation

> **Business problem:** RetailCo, a UK fashion retailer with 200 stores and 2M customers,
> migrates from on-premises SQL Server DWH to Microsoft Fabric to reduce costs by 60%
> and enable near-real-time analytics with Power BI DirectLake.

## Architecture

```
Open-Meteo / Faker (data source)
        │
        ▼
data/onelake/RetailCo.Lakehouse/
├── Files/bronze/               ← OneLake Files section (unmanaged Parquet)
│   ├── orders.parquet          ← 200,000 e-commerce transactions
│   ├── products.parquet        ← 200 product SKUs
│   └── customers.parquet       ← 10,000 customers
│
└── Tables/                     ← OneLake Tables section (managed Delta)
    ├── silver/orders           ← Joined, enriched, filtered
    └── gold/
        ├── fct_revenue_daily   ← Daily revenue by category/region/channel
        └── dim_customer_ltv    ← Customer lifetime value

data/retailco_lakehouse.duckdb  ← SQL Analytics Endpoint (T-SQL)
    ├── SCHEMA silver           ← View into Tables/silver/
    └── SCHEMA gold             ← Powers Power BI DirectLake
```

## Tech Stack

| Layer | Technology | Real Fabric Equivalent |
|---|---|---|
| Storage | Parquet files | OneLake (ADLS Gen2) |
| Analytics DB | DuckDB 1.5 | SQL Analytics Endpoint |
| Transformation | Python + pandas | Fabric Notebook (PySpark) |
| Data generation | Faker + numpy | CRM mirroring / Eventstream |

## Files

| File | Purpose |
|---|---|
| `lakehouse.py` | Full Bronze→Silver→Gold pipeline with 200K e-commerce orders |
| `notebooks/01_exploration.ipynb` | Interactive Bronze data profiling |
| `notebooks/02_transformation.ipynb` | Silver transformation walkthrough |
| `notebooks/03_reporting.ipynb` | Gold reporting & KPIs |
| `fabric_concepts.md` | Deep-dive: OneLake, DirectLake, Shortcuts, Mirroring |

## Quick Start

```bash
pip install -r requirements.txt
python lakehouse.py
jupyter lab notebooks/
```

## Business Results (simulated)

| Metric | Before (SQL Server) | After (Fabric) |
|---|---|---|
| Report refresh latency | 24 hours | < 1 hour |
| Infrastructure cost | $8,000/month | $4,200/month (Fabric F64) |
| BI user onboarding | DBA help needed | Self-service Power BI |
| Data engineering effort | 40 hrs/month | 15 hrs/month |

## Design Considerations

- **DirectLake**: "Power BI reads Delta files directly from OneLake — no data import,
  no DirectQuery overhead. Sub-second refresh on billions of rows."
- **OneLake vs ADLS**: "OneLake IS ADLS Gen2, but with a single namespace per Fabric
  tenant. Every Lakehouse, Warehouse, and notebook sees the same storage."
- **Shortcuts**: "Zero-copy pointers to external storage. Our supplier data on S3
  appears as a Delta table in 60 seconds — no pipeline."
- **Key result**: "I ran a GROUP BY on 200K orders in DuckDB locally in 40ms —
  the same query pattern the Fabric SQL Warehouse runs on billions of rows via Photon."
