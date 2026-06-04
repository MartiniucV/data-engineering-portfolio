"""
Databricks Approach — RetailBank Transaction Analytics
=======================================================
Business Context: Same as fabric_approach.py
    RetailBank processes 10M daily transactions; needs daily risk reports,
    self-service analytics, and 7-year regulatory data retention.

Databricks approach characteristics:
    - Code-first: Python/PySpark is the primary interface (better for ML teams)
    - Delta Lake: full ACID, time travel, MERGE, OPTIMIZE
    - Unity Catalog: fine-grained column-level access control
    - Databricks SQL Warehouse: serverless SQL for BI (auto-scaling, auto-pause)
    - MLflow integration: model tracking lives next to the data pipeline
    - Cost model: DBUs (Databricks Units) consumed per cluster-minute

Local simulation: pandas + DuckDB (mirrors Delta Lake / Databricks SQL)
Real Databricks: PySpark + Delta Lake + Unity Catalog + SQL Warehouse

Compare with fabric_approach.py to understand the platform trade-offs.
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

np.random.seed(2)

DATA_DIR  = Path("data/databricks_bank")
DATA_DIR.mkdir(parents=True, exist_ok=True)

N_TRANSACTIONS = 50_000
CURRENCIES     = ["GBP", "USD", "EUR", "JPY"]
TX_TYPES       = ["purchase", "withdrawal", "transfer", "refund", "fee"]
CATEGORIES     = ["retail", "travel", "food", "tech", "healthcare", "unknown"]


# ── Data generation (same as fabric_approach.py for fair comparison) ──────────

def generate_transactions(n: int = N_TRANSACTIONS) -> pd.DataFrame:
    """Identical to fabric_approach.py — same input, same business problem."""
    amounts = np.abs(np.random.exponential(scale=150, size=n)).clip(0.01, 50_000)
    return pd.DataFrame({
        "transaction_id":    [f"TXN-{i:010d}" for i in range(1, n + 1)],
        "account_id":        [f"ACC-{np.random.randint(10000, 99999)}" for _ in range(n)],
        "transaction_date":  pd.date_range("2024-01-01", periods=n, freq="10s").date,
        "transaction_time":  pd.date_range("2024-01-01", periods=n, freq="10s"),
        "amount":            amounts.round(2),
        "currency":          np.random.choice(CURRENCIES, n, p=[0.6, 0.2, 0.15, 0.05]),
        "transaction_type":  np.random.choice(TX_TYPES, n, p=[0.65, 0.12, 0.10, 0.08, 0.05]),
        "merchant_category": np.random.choice(CATEGORIES, n),
        "country_code":      np.random.choice(["GB", "US", "FR", "DE", "JP"], n, p=[0.7, 0.1, 0.08, 0.07, 0.05]),
        "is_international":  np.random.choice([True, False], n, p=[0.15, 0.85]),
        "is_contactless":    np.random.choice([True, False], n, p=[0.72, 0.28]),
    })


# ── DATABRICKS APPROACH: PySpark-style pipeline ───────────────────────────────
# Real Databricks: these functions run on a Spark cluster via PySpark API.
# Locally: pandas mirrors the same logical operations.

class DeltaTableSimulator:
    """
    Simulates Delta Lake table semantics locally with pandas + Parquet.

    Real Databricks operations → local equivalent:
        df.write.format("delta").saveAsTable("catalog.schema.table")  → to_parquet
        DeltaTable.forName(spark, "catalog.schema.table").history()   → _delta_log dict
        MERGE INTO table USING source ON ...                           → pd.merge + assign
        OPTIMIZE table ZORDER BY col                                   → sort + to_parquet
    """
    def __init__(self, path: Path, table_name: str):
        self.path        = path
        self.table_name  = table_name
        self._delta_log: list[dict] = []

    def write(self, df: pd.DataFrame, mode: str = "overwrite",
              partition_by: Optional[list[str]] = None) -> None:
        """df.write.format("delta").mode(mode).partitionBy(*partition_by).save(path)"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(self.path, index=False)
        self._delta_log.append({
            "version":    len(self._delta_log),
            "timestamp":  datetime.utcnow().isoformat(),
            "operation":  "WRITE",
            "mode":       mode,
            "rows":       len(df),
            "partitioned_by": partition_by or [],
        })

    def read(self) -> pd.DataFrame:
        """spark.read.format("delta").load(path) or spark.table("catalog.schema.table")"""
        return pd.read_parquet(self.path)

    def merge(self, source: pd.DataFrame, key: str) -> None:
        """
        MERGE INTO table USING source ON table.key = source.key
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
        Real Databricks: DeltaTable.merge() API — ACID upsert without locks.
        """
        existing = self.read() if self.path.exists() else pd.DataFrame()
        combined = pd.concat([existing, source], ignore_index=True)
        combined = combined.drop_duplicates(subset=[key], keep="last")
        self.write(combined, mode="merge")

    def history(self) -> pd.DataFrame:
        """DeltaTable.forPath(spark, path).history() — shows all table versions."""
        return pd.DataFrame(self._delta_log)

    def optimize(self, zorder_by: Optional[list[str]] = None) -> None:
        """
        OPTIMIZE table ZORDER BY (col1, col2)
        Compacts files + co-locates rows for data skipping.
        Auto Optimize in Databricks does this automatically on write.
        """
        if not self.path.exists():
            return
        df = self.read()
        if zorder_by:
            # Local approximation: sort by ZORDER columns (real ZORDER uses Z-curve)
            valid_cols = [c for c in zorder_by if c in df.columns]
            if valid_cols:
                df = df.sort_values(valid_cols).reset_index(drop=True)
        self.write(df, mode="optimize")
        logger.info("  OPTIMIZE ZORDER BY %s → %d rows compacted", zorder_by, len(df))


def databricks_pipeline(df: pd.DataFrame) -> None:
    """
    Databricks-style pipeline using Delta Lake patterns.

    Key differences vs Fabric approach:
        1. MERGE instead of TRUNCATE+INSERT — supports incremental updates
           without full table replacement (critical for 10M rows/day)
        2. OPTIMIZE ZORDER BY transaction_date — data skipping for date queries
        3. Row-level security via column filter (Unity Catalog)
        4. Schema evolution tracked in Delta log (no ALTER TABLE needed)
        5. Time travel: can query any historical version for audit purposes

    Real Databricks notebook structure (shown in comments):
    """
    # ── Bronze: raw ingestion ─────────────────────────────────────────────────
    # Real: df.write.format("delta").mode("append").save("abfss://raw@storage.dfs.core.windows.net/transactions/")
    # Real: registered in Unity Catalog as main.bronze.transactions
    bronze = DeltaTableSimulator(DATA_DIR / "bronze/transactions.parquet", "main.bronze.transactions")
    bronze.write(df, mode="append", partition_by=["transaction_date"])
    logger.info("Databricks Bronze: %d rows written (Delta append)", len(df))

    # ── Silver: validated + enriched ─────────────────────────────────────────
    # Real: df.write.format("delta").mode("overwrite").option("mergeSchema","true")
    #           .partitionBy("transaction_date").saveAsTable("main.silver.transactions")
    FX = {"GBP": 1.0, "USD": 0.79, "EUR": 0.86, "JPY": 0.005}
    raw_df = bronze.read()
    raw_df["transaction_time"] = pd.to_datetime(raw_df["transaction_time"], errors="coerce")

    silver_df = raw_df.copy()
    silver_df["fx_rate"]       = silver_df["currency"].map(FX).fillna(1.0)
    silver_df["amount_gbp"]    = (silver_df["amount"] * silver_df["fx_rate"]).round(4)
    silver_df["is_high_value"] = silver_df["amount"] > 5_000
    silver_df["is_flagged"]    = silver_df["is_international"] & (silver_df["amount"] > 500)
    silver_df["risk_score"]    = (
        (silver_df["amount"] / silver_df["amount"].quantile(0.99)).clip(0, 1) * 0.4
        + silver_df["is_flagged"].astype(float) * 0.4
        + silver_df["is_international"].astype(float) * 0.2
    ).round(4)
    silver_df["_silver_ts"]    = datetime.utcnow().isoformat()

    silver = DeltaTableSimulator(DATA_DIR / "silver/transactions.parquet", "main.silver.transactions")
    silver.write(silver_df, mode="overwrite", partition_by=["transaction_date"])

    # ── Gold: MERGE for incremental updates ───────────────────────────────────
    # Real: DeltaTable.forName(spark, "main.gold.daily_risk")
    #           .merge(source=daily_agg, condition="t.transaction_date = s.transaction_date AND t.merchant_category = s.merchant_category")
    #           .whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()
    silver_data = silver.read()
    silver_data["transaction_date"] = pd.to_datetime(silver_data["transaction_date"], errors="coerce").dt.date

    gold_df = (
        silver_data[silver_data["transaction_type"] != "fee"]
        .groupby(["transaction_date", "merchant_category", "country_code"])
        .agg(
            total_transactions=("transaction_id", "count"),
            total_volume_gbp=("amount_gbp", "sum"),
            avg_transaction_gbp=("amount_gbp", "mean"),
            high_value_count=("is_high_value", "sum"),
            flagged_count=("is_flagged", "sum"),
            avg_risk_score=("risk_score", "mean"),
        )
        .round({"total_volume_gbp": 2, "avg_transaction_gbp": 2, "avg_risk_score": 4})
        .reset_index()
    )
    gold_df["flag_rate_pct"] = (
        gold_df["flagged_count"] / gold_df["total_transactions"] * 100
    ).round(3)
    gold_df["_merge_key"] = (
        gold_df["transaction_date"].astype(str) + "_"
        + gold_df["merchant_category"] + "_" + gold_df["country_code"]
    )

    gold = DeltaTableSimulator(DATA_DIR / "gold/daily_risk.parquet", "main.gold.daily_risk")
    gold.merge(gold_df, key="_merge_key")  # MERGE = incremental update without full reload
    gold.optimize(zorder_by=["transaction_date", "merchant_category"])

    # ── Delta table history (time travel proof) ────────────────────────────────
    logger.info("\nDelta table history (gold.daily_risk):")
    logger.info("\n%s", gold.history().to_string(index=False))

    # ── Sample results ─────────────────────────────────────────────────────────
    logger.info("\n=== DATABRICKS: DAILY RISK REPORT SAMPLE ===")
    result = gold.read()
    logger.info("\n%s", (
        result.groupby("merchant_category")
        .agg(total_txn=("total_transactions", "sum"),
             vol_M_gbp=("total_volume_gbp", lambda x: round(x.sum()/1e6, 2)),
             flagged=("flagged_count", "sum"),
             avg_risk=("avg_risk_score", lambda x: round(x.mean(), 4)))
        .sort_values("vol_M_gbp", ascending=False)
        .to_string()
    ))

    logger.info("Databricks pipeline: silver=%d  gold=%d", len(silver_df), len(gold_df))
    logger.info("Cost note: Databricks Jobs compute ~$0.20/hr (e2-standard-4 DBU pricing)")
    logger.info("           SQL Warehouse (serverless): auto-pauses after 10min idle → $0/idle")
    logger.info("           vs Fabric F64: ~$4K/month flat regardless of usage")


def run() -> None:
    df = generate_transactions()
    databricks_pipeline(df)
    logger.info("Databricks approach complete. Compare outputs with fabric_approach.py.")
    logger.info("See decision_framework.md for when to choose each platform.")


if __name__ == "__main__":
    run()
