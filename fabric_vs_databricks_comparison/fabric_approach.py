"""
Microsoft Fabric Approach — RetailBank Transaction Analytics
============================================================
Business Context:
    RetailBank processes 10M daily credit card transactions and needs to:
      - Produce daily risk reports for the Compliance team (T+2 hours)
      - Enable self-service analytics for 200 business analysts
      - Maintain 7-year data retention for regulatory purposes

Fabric approach characteristics:
    - T-SQL-centric: business analysts write SQL, not Python/Spark
    - Power BI DirectLake: zero-copy BI, no dataset refresh needed
    - OneLake: single storage layer for all Fabric workloads
    - Fabric Pipelines: low-code ETL for non-engineers
    - Cost model: Fabric capacity (CU) shared across all workloads

Local simulation: DuckDB (T-SQL compatible) + Parquet
Real Fabric: OneLake + Delta + SQL Analytics Endpoint + Power BI
"""
import logging
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from faker import Faker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

Faker.seed(1)
np.random.seed(1)
fake = Faker()

DB_PATH   = "data/fabric_bank.duckdb"
DATA_DIR  = Path("data/fabric_bank")
DATA_DIR.mkdir(parents=True, exist_ok=True)

N_TRANSACTIONS = 50_000
CURRENCIES = ["GBP", "USD", "EUR", "JPY"]
TX_TYPES   = ["purchase", "withdrawal", "transfer", "refund", "fee"]
RISK_CATEGORIES = ["retail", "travel", "food", "tech", "healthcare", "unknown"]


def generate_transactions(n: int = N_TRANSACTIONS) -> pd.DataFrame:
    """Generate bank transaction data. Simulates data arriving from Core Banking System."""
    amounts = np.abs(np.random.exponential(scale=150, size=n)).clip(0.01, 50_000)
    return pd.DataFrame({
        "transaction_id":   [f"TXN-{i:010d}" for i in range(1, n + 1)],
        "account_id":       [f"ACC-{np.random.randint(10000, 99999)}" for _ in range(n)],
        "transaction_date": pd.date_range("2024-01-01", periods=n, freq="10s").date,
        "transaction_time": pd.date_range("2024-01-01", periods=n, freq="10s"),
        "amount":           amounts.round(2),
        "currency":         np.random.choice(CURRENCIES, n, p=[0.6, 0.2, 0.15, 0.05]),
        "transaction_type": np.random.choice(TX_TYPES, n, p=[0.65, 0.12, 0.10, 0.08, 0.05]),
        "merchant_category": np.random.choice(RISK_CATEGORIES, n),
        "country_code":     np.random.choice(["GB", "US", "FR", "DE", "JP"], n, p=[0.7, 0.1, 0.08, 0.07, 0.05]),
        "is_international": np.random.choice([True, False], n, p=[0.15, 0.85]),
        "is_contactless":   np.random.choice([True, False], n, p=[0.72, 0.28]),
    })


# ── FABRIC APPROACH: T-SQL in DuckDB (mirrors Fabric SQL Analytics Endpoint) ──

def fabric_pipeline(con: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> None:
    """
    Fabric-style pipeline:
        1. Land raw data in Lakehouse (Files section, Parquet)
        2. Register as Table via Spark notebook or COPY INTO
        3. Run T-SQL transformations via SQL Analytics Endpoint
        4. Power BI connects via DirectLake semantic model

    Key Fabric advantage: T-SQL is accessible to ALL analysts without
    Spark/Python knowledge. The SQL Analytics Endpoint exposes every
    Delta table in the Lakehouse as a T-SQL view.
    """
    # Step 1: Bronze — raw Parquet in Lakehouse Files section
    raw_path = DATA_DIR / "raw_transactions.parquet"
    df.to_parquet(raw_path, index=False)
    logger.info("Fabric Bronze: %d rows → %s", len(df), raw_path)

    # Step 2-4: Silver + Gold via T-SQL (SQL Analytics Endpoint)
    # Real Fabric: run these in the Fabric SQL Editor or a notebook SQL cell
    # The SQL Analytics Endpoint auto-generates these views when you save to Tables/

    con.execute(f"""
        -- Silver: clean and enrich
        -- Real Fabric: CREATE TABLE silver.transactions AS SELECT ... (runs on Spark)
        CREATE OR REPLACE TABLE silver_transactions AS
        SELECT
            transaction_id,
            account_id,
            CAST(transaction_time AS TIMESTAMP)                 AS transaction_ts,
            CAST(transaction_date AS DATE)                      AS transaction_date,
            amount,
            currency,
            -- FX normalisation to GBP (Fabric: lookup from SQL reference table)
            CASE currency
                WHEN 'GBP' THEN amount
                WHEN 'USD' THEN amount * 0.79
                WHEN 'EUR' THEN amount * 0.86
                WHEN 'JPY' THEN amount * 0.005
                ELSE amount
            END                                                 AS amount_gbp,
            transaction_type,
            merchant_category,
            country_code,
            is_international,
            is_contactless,
            -- Risk flags (real Fabric: these feed a Power BI risk dashboard)
            (amount > 5000)                                     AS is_high_value,
            (is_international AND amount > 500)                 AS is_flagged,
            CURRENT_TIMESTAMP                                   AS _fabric_pipeline_ts
        FROM read_parquet('{raw_path}')
        WHERE amount > 0
          AND transaction_type != 'fee'  -- exclude internal bank fees
    """)

    con.execute("""
        -- Gold: daily risk summary
        -- Real Fabric: stored as Delta table in Tables/ → DirectLake semantic model
        -- Power BI reads this table DIRECTLY from OneLake — no import, no refresh
        CREATE OR REPLACE TABLE gold_daily_risk AS
        SELECT
            transaction_date,
            merchant_category,
            country_code,
            COUNT(*)                                        AS total_transactions,
            ROUND(SUM(amount_gbp), 2)                       AS total_volume_gbp,
            ROUND(AVG(amount_gbp), 2)                       AS avg_transaction_gbp,
            SUM(CAST(is_high_value AS INTEGER))             AS high_value_count,
            SUM(CAST(is_flagged AS INTEGER))                AS flagged_count,
            ROUND(
                SUM(CAST(is_flagged AS INTEGER)) * 100.0 / COUNT(*),
                3
            )                                               AS flag_rate_pct
        FROM silver_transactions
        GROUP BY transaction_date, merchant_category, country_code
        ORDER BY transaction_date, total_volume_gbp DESC
    """)

    # Sample the results (Power BI equivalent: KPI card + table visual)
    logger.info("=== FABRIC: DAILY RISK REPORT SAMPLE ===")
    logger.info("\n%s", con.execute("""
        SELECT
            merchant_category,
            SUM(total_transactions)                         AS total_txn,
            ROUND(SUM(total_volume_gbp)/1e6, 2)             AS vol_M_gbp,
            SUM(flagged_count)                              AS flagged,
            ROUND(AVG(flag_rate_pct), 3)                    AS avg_flag_rate_pct
        FROM gold_daily_risk
        GROUP BY merchant_category
        ORDER BY vol_M_gbp DESC
        LIMIT 8
    """).df().to_string(index=False))

    silver_count = con.execute("SELECT COUNT(*) FROM silver_transactions").fetchone()[0]
    gold_count   = con.execute("SELECT COUNT(*) FROM gold_daily_risk").fetchone()[0]
    logger.info("Fabric pipeline: silver=%d  gold=%d", silver_count, gold_count)
    logger.info("Fabric DirectLake: Power BI would connect directly to gold_daily_risk Delta table")
    logger.info("Cost note: Fabric F64 capacity (~$4,000/month) handles this pipeline + 200 BI users")


def run() -> None:
    df  = generate_transactions()
    con = duckdb.connect(DB_PATH)
    con.execute("CREATE SCHEMA IF NOT EXISTS silver")
    con.execute("CREATE SCHEMA IF NOT EXISTS gold")
    fabric_pipeline(con, df)
    con.close()
    logger.info("Fabric approach complete. See databricks_approach.py for comparison.")


if __name__ == "__main__":
    run()
