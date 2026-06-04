"""
ADF Copy Activity Simulation — FinanceFlow Transaction Consolidation
====================================================================
Business Problem:
    FinanceFlow, a Series-B fintech startup, processes 500K daily payment
    transactions from three disparate sources. Finance and compliance teams
    need a unified, auditable view within 2 hours of transaction occurrence
    for regulatory reporting (PSD2, MiFID II).

Source landscape (simulated locally → real ADF equivalent):
    Source 1: REST API      → real ADF: HTTP Connector + linked service
    Source 2: CSV file drop → real ADF: ADLS Gen2 source with wildcard path
    Source 3: PostgreSQL    → real ADF: Azure SQL / PostgreSQL connector

This script simulates ADF Copy Activity:
    - Source connector (read data)
    - Schema mapping (field rename/cast)
    - Sink connector (write to destination)
    - Fault tolerance (skip bad rows, write error file)
    - Activity run metrics (rows read, rows written, throughput)

Real ADF Copy Activity supports 90+ source/sink connectors with zero-code
configuration. This Python equivalent makes the logic explicit for learning.
"""
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from faker import Faker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

Faker.seed(0)
np.random.seed(0)
fake = Faker()

DATA_DIR = Path("data/adf_simulation")
DATA_DIR.mkdir(parents=True, exist_ok=True)

SINK_PATH     = DATA_DIR / "sink/unified_transactions.parquet"
ERROR_LOG_PATH = DATA_DIR / "sink/error_log.csv"
SINK_PATH.parent.mkdir(parents=True, exist_ok=True)


# ── Activity run metrics (mirrors ADF Monitor → Pipeline Run → Activity details) ──

@dataclass
class ActivityRunMetrics:
    """
    Mirrors the metrics visible in ADF Monitor for a Copy Activity run.
    Real ADF: accessible via Azure Monitor, Log Analytics, or REST API.
    """
    activity_name: str
    run_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    rows_read: int = 0
    rows_written: int = 0
    rows_skipped: int = 0
    data_read_mb: float = 0.0
    data_written_mb: float = 0.0
    status: str = "InProgress"

    def finish(self, status: str = "Succeeded") -> None:
        self.end_time = datetime.utcnow()
        self.status   = status

    def duration_seconds(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    def throughput_rows_per_sec(self) -> float:
        d = self.duration_seconds()
        return self.rows_written / d if d > 0 else 0.0

    def log(self) -> None:
        logger.info(
            "[%s] run_id=%s  status=%s  read=%d  written=%d  skipped=%d  "
            "duration=%.2fs  throughput=%.0f rows/s",
            self.activity_name, self.run_id, self.status,
            self.rows_read, self.rows_written, self.rows_skipped,
            self.duration_seconds(), self.throughput_rows_per_sec(),
        )


# ── Schema mapping (ADF: column mapping tab in Copy Activity) ──────────────────

# Each entry: {source_field: (target_field, cast_function)}
API_SCHEMA_MAP: dict[str, tuple[str, Any]] = {
    "txn_id":           ("transaction_id",   str),
    "ts":               ("transaction_time", pd.to_datetime),
    "amt":              ("amount_usd",        float),
    "ccy":              ("currency",          str),
    "merchant_name":    ("merchant",          str),
    "txn_type":         ("transaction_type",  str),
    "user_id":          ("customer_id",       str),
}

CSV_SCHEMA_MAP: dict[str, tuple[str, Any]] = {
    "TransactionID":    ("transaction_id",   str),
    "Timestamp":        ("transaction_time", pd.to_datetime),
    "Amount":           ("amount_usd",        float),
    "Currency":         ("currency",          str),
    "MerchantName":     ("merchant",          str),
    "Type":             ("transaction_type",  str),
    "CustomerID":       ("customer_id",       str),
}

DB_SCHEMA_MAP: dict[str, tuple[str, Any]] = {
    "transaction_id":   ("transaction_id",   str),
    "created_at":       ("transaction_time", pd.to_datetime),
    "amount":           ("amount_usd",        float),
    "currency_code":    ("currency",          str),
    "merchant":         ("merchant",          str),
    "type":             ("transaction_type",  str),
    "cust_id":          ("customer_id",       str),
}


# ── Source connectors ─────────────────────────────────────────────────────────

def source_from_api(n: int = 10_000) -> pd.DataFrame:
    """
    Simulate reading from a REST API (e.g. payment processor webhook).
    Real ADF: HTTP Connector + pagination settings + linked service with
    bearer token stored in Azure Key Vault (never hard-coded).
    """
    logger.info("[Source 1/3] Reading %d transactions from REST API simulation...", n)
    amounts = np.abs(np.random.normal(loc=85, scale=120, size=n)).clip(0.01, 5000)
    return pd.DataFrame({
        "txn_id":        [str(uuid.uuid4()) for _ in range(n)],
        "ts":            [fake.date_time_between("-30d", "now").isoformat() for _ in range(n)],
        "amt":           amounts.round(2),
        "ccy":           np.random.choice(["USD", "EUR", "GBP"], n, p=[0.5, 0.3, 0.2]),
        "merchant_name": [fake.company() for _ in range(n)],
        "txn_type":      np.random.choice(["purchase", "refund", "transfer"], n, p=[0.80, 0.12, 0.08]),
        "user_id":       [f"U{random.randint(10000, 99999)}" for _ in range(n)],
        # Inject some nulls to test fault tolerance
        "extra_field":   np.random.choice([None, "extra"], n, p=[0.9, 0.1]),
    })


def source_from_csv(n: int = 5_000) -> pd.DataFrame:
    """
    Simulate reading from a CSV file drop on ADLS Gen2.
    Real ADF: Delimited Text dataset with wildcard path
    'raw/transactions/yyyy/mm/dd/*.csv' for daily partitioned drops.
    Auto-trigger: Storage Event Trigger fires when new blob arrives.
    """
    logger.info("[Source 2/3] Reading %d transactions from CSV drop simulation...", n)
    csv_path = DATA_DIR / "source/transactions_batch.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    import random
    amounts = np.abs(np.random.normal(loc=210, scale=300, size=n)).clip(1, 50000)
    df = pd.DataFrame({
        "TransactionID": [f"CSV-{uuid.uuid4().hex[:12].upper()}" for _ in range(n)],
        "Timestamp":     [fake.date_time_between("-30d", "now").isoformat() for _ in range(n)],
        "Amount":        amounts.round(2),
        "Currency":      np.random.choice(["USD", "EUR", "GBP", "JPY"], n, p=[0.4, 0.3, 0.2, 0.1]),
        "MerchantName":  [fake.company() for _ in range(n)],
        "Type":          np.random.choice(["purchase", "refund", "wire_transfer"], n, p=[0.70, 0.15, 0.15]),
        "CustomerID":    [f"C{random.randint(100000, 999999)}" for _ in range(n)],
    })
    df.to_csv(csv_path, index=False)
    return pd.read_csv(csv_path)


def source_from_database(n: int = 8_000) -> pd.DataFrame:
    """
    Simulate reading from PostgreSQL (or Azure SQL DB) replica.
    Real ADF: Copy Activity with 'Query' mode — run a SELECT with watermark
    to pull only new rows since last successful run.
    Watermark: stored in ADF pipeline parameter, updated after each run.
    """
    import random
    logger.info("[Source 3/3] Reading %d transactions from database simulation...", n)
    amounts = np.abs(np.random.exponential(scale=150, size=n)).clip(0.50, 100000)
    return pd.DataFrame({
        "transaction_id": [f"DB-{uuid.uuid4().hex[:16]}" for _ in range(n)],
        "created_at":     [fake.date_time_between("-30d", "now").isoformat() for _ in range(n)],
        "amount":         amounts.round(2),
        "currency_code":  np.random.choice(["USD", "EUR", "GBP"], n, p=[0.6, 0.25, 0.15]),
        "merchant":       [fake.company() for _ in range(n)],
        "type":           np.random.choice(["purchase", "chargeback", "adjustment"], n, p=[0.85, 0.10, 0.05]),
        "cust_id":        [f"DB-CUST-{random.randint(1, 100000):06d}" for _ in range(n)],
    })


# ── Schema mapper (ADF: column mapping configuration) ─────────────────────────

def apply_schema_mapping(
    df: pd.DataFrame,
    schema_map: dict[str, tuple[str, Any]],
    activity_name: str,
) -> tuple[pd.DataFrame, list[dict]]:
    """
    Apply field rename + type cast from source schema to target schema.
    Returns (mapped_df, error_rows).

    Real ADF: configured visually in the 'Mapping' tab of Copy Activity.
    Type mismatches are logged to ADF Monitor; rows are skipped or the
    activity fails based on fault-tolerance settings.
    """
    errors: list[dict] = []
    mapped_rows: list[dict] = []

    # Only keep columns present in the schema map
    source_cols = [c for c in schema_map if c in df.columns]
    df_sub = df[source_cols].copy()

    for _, row in df_sub.iterrows():
        mapped: dict = {"_source": activity_name}
        ok = True
        for src_col, (tgt_col, cast_fn) in schema_map.items():
            if src_col not in row:
                continue
            try:
                mapped[tgt_col] = cast_fn(row[src_col])
            except (ValueError, TypeError) as exc:
                errors.append({"row": row.to_dict(), "error": str(exc), "source": activity_name})
                ok = False
                break
        if ok:
            mapped_rows.append(mapped)

    return pd.DataFrame(mapped_rows), errors


# ── Sink writer (ADF: sink dataset configuration) ─────────────────────────────

def write_sink(dfs: list[pd.DataFrame], metrics: ActivityRunMetrics) -> None:
    """
    Union all sources and write to the sink (Parquet / Delta on ADLS Gen2).

    Real ADF sink options:
      - Azure Data Lake Storage Gen2 (Parquet, Delta)
      - Azure SQL Database / Synapse Analytics (bulk insert)
      - Fabric Lakehouse (via Fabric pipeline connector)
      - Databricks Delta (via Databricks connector)

    Cost optimisation: write Parquet with snappy compression.
    At 1M rows/day, storage cost ≈ $0.05/month on ADLS Gen2.
    """
    combined = pd.concat(dfs, ignore_index=True)

    # Add sink-side audit columns (ADF adds these via 'Additional columns' config)
    combined["_pipeline_run_id"] = metrics.run_id
    combined["_loaded_at"]        = datetime.utcnow().isoformat()

    # Deduplicate on transaction_id (last-write-wins — same as ADF Upsert mode)
    before = len(combined)
    combined = combined.drop_duplicates(subset=["transaction_id"], keep="last")
    dupes = before - len(combined)
    if dupes:
        logger.info("Deduplication: removed %d duplicate transaction_ids", dupes)

    combined.to_parquet(SINK_PATH, index=False)

    metrics.rows_written    = len(combined)
    metrics.data_written_mb = SINK_PATH.stat().st_size / 1_048_576


# ── Main copy activity ─────────────────────────────────────────────────────────

def run_copy_activity() -> ActivityRunMetrics:
    """
    Orchestrate the full Copy Activity: 3 sources → mapping → unified sink.

    Real ADF Copy Activity parallel copy:
      - parallelCopies: 4 (4 concurrent read threads per source)
      - For ADLS Gen2 source: staged copy via Azure Blob improves throughput
      - Achievable throughput: 1–4 GB/min depending on source/sink type
    """
    metrics = ActivityRunMetrics("CopyActivity_UnifyTransactions")
    logger.info("Starting ADF Copy Activity simulation (run_id=%s)", metrics.run_id)

    all_errors: list[dict] = []
    mapped_dfs: list[pd.DataFrame] = []

    sources = [
        (source_from_api,      API_SCHEMA_MAP, "REST_API_source"),
        (source_from_csv,      CSV_SCHEMA_MAP, "CSV_file_drop"),
        (source_from_database, DB_SCHEMA_MAP,  "PostgreSQL_replica"),
    ]

    total_read = 0
    for source_fn, schema_map, name in sources:
        raw_df          = source_fn()
        total_read      += len(raw_df)
        mapped_df, errs = apply_schema_mapping(raw_df, schema_map, name)
        mapped_dfs.append(mapped_df)
        all_errors.extend(errs)
        logger.info("  %-25s  read=%d  mapped=%d  errors=%d",
                    name, len(raw_df), len(mapped_df), len(errs))

    metrics.rows_read    = total_read
    metrics.rows_skipped = len(all_errors)

    write_sink(mapped_dfs, metrics)

    # Write error log (ADF: 'Fault tolerance' → 'Log settings' → error file on ADLS)
    if all_errors:
        pd.DataFrame(all_errors).to_csv(ERROR_LOG_PATH, index=False)
        logger.warning("Wrote %d error rows to %s", len(all_errors), ERROR_LOG_PATH)

    metrics.finish("Succeeded")
    metrics.log()
    return metrics


if __name__ == "__main__":
    import random
    run_copy_activity()
    logger.info("Sink file: %s", SINK_PATH)
