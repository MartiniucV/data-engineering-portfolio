# Full Data Platform — Capstone Project

An end-to-end data engineering platform that ingests live weather data from a
public API, transforms and loads it into PostgreSQL, validates it with a quality
framework, and visualises it in an interactive Streamlit dashboard.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         Full Data Platform                                   │
│                                                                              │
│   Open-Meteo API (free, no key)                                              │
│         │                                                                    │
│         ▼                                                                    │
│   ┌─────────────┐   Parquet    ┌───────────────┐   PostgreSQL               │
│   │  ingest.py  │ ──────────▶  │ transform.py  │ ──────────▶  weather_daily │
│   │             │              │               │              table          │
│   │ 5 cities    │  data/       │ clean + enrich│                │            │
│   │ 90-day      │  weather_raw │ load to DB    │                │            │
│   │ daily data  │  .parquet    │               │                │            │
│   └─────────────┘              └───────────────┘                │            │
│                                                                  │            │
│                          ┌───────────────┐                      │            │
│                          │  quality.py   │ ◀────────────────────┘            │
│                          │               │                                   │
│                          │ 14 assertions │                                   │
│                          │ exits 1 on    │                                   │
│                          │ failure       │                                   │
│                          └───────────────┘                                   │
│                                                                              │
│                          ┌───────────────┐                                   │
│                          │ dashboard.py  │ ◀── reads PostgreSQL              │
│                          │               │                                   │
│                          │  Streamlit    │                                   │
│                          │  :8501        │                                   │
│                          └───────────────┘                                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Data source | Open-Meteo REST API (free, no API key) |
| Ingestion | Python `requests`, `pandas` |
| Storage (raw) | Apache Parquet (`pyarrow`) |
| Storage (processed) | PostgreSQL 15 |
| ORM / DB client | SQLAlchemy 2.x + `psycopg2` |
| Data quality | Custom assertion framework (pandas) |
| Dashboard | Streamlit 1.x |
| Language | Python 3.10+ |

## Project Structure

```
capstone/
├── ingest.py        # Fetches Open-Meteo data → Parquet
├── transform.py     # Cleans Parquet → PostgreSQL
├── quality.py       # 14 data quality assertions
├── dashboard.py     # Streamlit dashboard
├── requirements.txt
├── data/            # Auto-created; holds weather_raw.parquet (git-ignored)
└── README.md
```

## Data Pipeline Steps

### 1. `ingest.py`
- Calls the Open-Meteo `/v1/forecast` endpoint for **New York, London, Tokyo,
  Sydney, Sao Paulo**
- Fetches the last **90 days** of daily metrics:
  `temperature_2m_max`, `temperature_2m_min`, `precipitation_sum`,
  `wind_speed_10m_max`, `weather_code`
- Saves ~450 rows as `data/weather_raw.parquet`

### 2. `transform.py`
- Loads the Parquet file
- Cleaning rules:
  - Drops rows with nulls in required columns
  - Enforces temperature bounds: −80 °C to +60 °C
  - Clips negative precipitation / wind values to 0
- Derives `temp_range = max_temp − min_temp`
- Truncates and reloads `weather_daily` in PostgreSQL (idempotent)

### 3. `quality.py`
Runs 14 assertions covering:
- **Volume**: row count ≥ 100
- **Completeness**: no NULLs in key columns
- **Coverage**: all 5 expected cities present
- **Range validity**: temperatures within physical bounds, max ≥ min
- **Consistency**: `temp_range` matches the derived formula
- **Uniqueness**: no duplicate `(date, city)` pairs
- **Recency**: date span ≥ 30 days

Exit code `0` = all checks pass. Exit code `1` = at least one failure.

### 4. `dashboard.py`
Interactive Streamlit app with:
- City + date-range sidebar filters
- KPI row (record count, avg temps, precipitation, wind)
- Line chart: daily max temperature per city
- Bar chart: daily precipitation per city
- Area chart: daily wind speed per city
- Summary statistics table per city
- Raw data expander

## Prerequisites

- Python 3.10+
- PostgreSQL running on `localhost:5432`
  - User: `vlad`, Password: `vlad123`, Database: `portfolio`

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Ingest weather data (creates data/weather_raw.parquet)
python ingest.py

# 3. Clean and load into PostgreSQL
python transform.py

# 4. Validate data quality (exits 1 on failure)
python quality.py

# 5. Launch the dashboard
streamlit run dashboard.py
# Open http://localhost:8501
```

## Configuration

| Variable | Location | Default | Description |
|----------|----------|---------|-------------|
| `DB_URL` | transform.py / quality.py / dashboard.py | `postgresql://vlad:vlad123@localhost:5432/portfolio` | PostgreSQL connection string |
| `days_back` | ingest.py `ingest()` | `90` | Historical days to fetch |
| `TABLE` | transform.py / quality.py / dashboard.py | `weather_daily` | Target table name |

## Key Design Decisions

- **Idempotent loads** — `transform.py` issues a `TRUNCATE … RESTART IDENTITY`
  before inserting, so reruns never produce duplicates.
- **Parquet as intermediate format** — decouples ingestion from transformation;
  the raw file can be reprocessed without re-hitting the API.
- **Assertion-based quality framework** — a lightweight alternative to
  `great_expectations` that produces the same exit-code contract and detailed
  per-check logging, with zero configuration overhead.
- **Streamlit caching** — `@st.cache_data(ttl=300)` avoids redundant DB queries
  across user interactions within a 5-minute window.
