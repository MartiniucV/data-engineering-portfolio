"""
Databricks AutoLoader Pattern — ManufactureX Incremental IoT Ingestion
=======================================================================
Business Context:
    ManufactureX's 10,000 sensors emit 2 readings/min each.
    New Parquet files land on ADLS Gen2 every 5 minutes per plant.
    The pipeline must ingest only NEW files without re-processing old ones,
    and survive restarts without duplicates.

AutoLoader (cloudFiles) advantages over traditional glob read:
    - Schema inference:   auto-detects column types, evolves schema automatically
    - Change tracking:    uses file notification or directory listing to find new files only
    - Exactly-once:       checkpoint-based — restart-safe with no duplicate rows
    - Scalability:        handles millions of files; listing overhead = O(new files) not O(all)
    - Schema hints:       provide partial hints, AutoLoader infers the rest

This script simulates AutoLoader behaviour locally:
    Real Databricks:             Local simulation:
    ─────────────────────        ─────────────────────────────
    spark.readStream             pandas.read_parquet (batch mode)
      .format("cloudFiles")      file change tracking via JSON checkpoint
      .option("cloudFiles.format","parquet")
      .option("checkpointLocation", ...)
      .load("abfss://...")
    .writeStream                 direct Parquet append
      .format("delta")
      .option("checkpointLocation",...)
      .start(silver_path)
"""
import json
import logging
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

RAW_ROOT        = Path("data/adls_simulation/sensor-data/raw")
SILVER_PATH     = Path("data/adls_simulation/sensor-data/silver/sensor_readings.parquet")
CHECKPOINT_PATH = Path("data/adls_simulation/checkpoints/autoloader_sensor_readings.json")

# ── AutoLoader checkpoint simulation ─────────────────────────────────────────

def load_checkpoint() -> set[str]:
    """
    Load the set of already-processed file paths.

    Real Databricks AutoLoader: checkpoint stored on ADLS Gen2 / DBFS as
    binary RocksDB files under the checkpointLocation directory.
    Includes Kafka-style offset log — not just file names but sequence IDs.
    """
    if CHECKPOINT_PATH.exists():
        data = json.loads(CHECKPOINT_PATH.read_text())
        return set(data.get("processed_files", []))
    return set()


def save_checkpoint(processed: set[str]) -> None:
    """Persist the checkpoint. Real AutoLoader does this atomically per micro-batch."""
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(json.dumps({
        "processed_files": sorted(processed),
        "last_updated":    datetime.utcnow().isoformat(),
        "schema_version":  1,
    }, indent=2))


# ── Schema inference ──────────────────────────────────────────────────────────

def infer_schema(sample_files: list[Path]) -> dict[str, str]:
    """
    Infer schema from a sample of incoming files.

    Real AutoLoader (cloudFiles.inferColumnTypes=true):
        Samples up to cloudFiles.schemaHints.maxFilesToSample (default: 50)
        Writes inferred schema to checkpointLocation/_schemas/
        On schema evolution (new column): rescues unknown columns into
        _rescued_data JSON column rather than failing the pipeline.

    This is critical for IoT pipelines where sensor firmware updates
    sometimes add new telemetry fields without advance notice.
    """
    if not sample_files:
        return {}
    sample = pd.read_parquet(sample_files[0])
    return {col: str(dtype) for col, dtype in sample.dtypes.items()}


# ── Quality validation (AutoLoader + Delta Expectations) ─────────────────────

def validate_batch(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Apply data quality rules to incoming batch.

    Real Databricks Delta Live Tables (DLT) — the preferred way to add
    quality checks to AutoLoader pipelines:

        @dlt.expect("valid_temperature", "temperature_c BETWEEN -40 AND 200")
        @dlt.expect_or_drop("non_null_sensor", "sensor_id IS NOT NULL")
        @dlt.expect_or_quarantine("valid_pressure", "pressure_bar > 0",
                                   quarantine_table="sensor_quarantine")
        @dlt.table
        def silver_sensor_readings():
            return dlt.read_stream("bronze_raw_sensors")

    Locally: pandas-based quality gates with explicit quarantine split.
    """
    valid_mask = (
        df["temperature_c"].between(-40, 200)
        & df["pressure_bar"].between(0, 20)
        & df["vibration_hz"].between(0, 100)
        & df["sensor_id"].notna()
        & df["timestamp"].notna()
    )
    valid     = df[valid_mask].copy()
    quarantine = df[~valid_mask].copy()

    if not quarantine.empty:
        quarantine["_quarantine_reason"] = "failed_sensor_range_check"
        quarantine["_quarantine_ts"]     = datetime.utcnow().isoformat()

    return valid, quarantine


# ── Silver enrichment ─────────────────────────────────────────────────────────

def enrich_silver(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply Silver-layer transformations.

    Real Databricks: these derived columns are computed by Photon engine
    as part of a DLT pipeline or streaming Structured Streaming job.
    On 10B rows/year, ZORDER BY (plant_id, timestamp) cuts query cost by ~80%.
    """
    df = df.copy()
    df["timestamp"]         = pd.to_datetime(df["timestamp"], errors="coerce")
    df["ingest_date"]       = df["timestamp"].dt.date
    df["ingest_hour"]       = df["timestamp"].dt.hour

    # Derived: temperature anomaly flag (> 3 std-devs from plant mean)
    plant_stats = df.groupby("plant_id")["temperature_c"].agg(["mean", "std"]).rename(
        columns={"mean": "plant_temp_mean", "std": "plant_temp_std"}
    )
    df = df.join(plant_stats, on="plant_id")
    df["temp_z_score"]      = (
        (df["temperature_c"] - df["plant_temp_mean"])
        / df["plant_temp_std"].replace(0, np.nan)
    ).round(3)
    df["is_temp_anomaly"]   = df["temp_z_score"].abs() > 3.0
    df["_autoloader_batch"] = datetime.utcnow().isoformat()

    return df.drop(columns=["plant_temp_mean", "plant_temp_std"])


# ── Main AutoLoader simulation ────────────────────────────────────────────────

def run_autoloader(reset_checkpoint: bool = False) -> None:
    """
    Scan for new files, process only unprocessed ones.

    Real Databricks AutoLoader deployment:
        - Runs as a Databricks Job on a single-node cluster (cost: ~$0.10/hr)
        - Scheduled every 5 minutes OR triggered by ADLS file-arrival event
        - Can also run as a continuous stream (awaitTermination())
        - 10,000 sensors × 5-min batches = ~2,880 files/day per plant → 34,560 files/day total
    """
    if reset_checkpoint:
        if CHECKPOINT_PATH.exists():
            CHECKPOINT_PATH.unlink()
        logger.info("Checkpoint reset.")

    processed = load_checkpoint()
    logger.info("Checkpoint: %d files already processed", len(processed))

    # Discover all Parquet files in raw landing zone (AutoLoader: directory listing mode)
    all_files = sorted(RAW_ROOT.rglob("*.parquet"))
    new_files  = [f for f in all_files if str(f) not in processed]
    logger.info("New files to process: %d / %d total", len(new_files), len(all_files))

    if not new_files:
        logger.info("No new files. AutoLoader would sleep until next trigger.")
        return

    # Infer schema from first new file
    schema = infer_schema(new_files[:3])
    logger.info("Inferred schema (%d columns): %s", len(schema), list(schema.keys())[:8])

    # Process new files in micro-batches (AutoLoader: processingTime trigger)
    BATCH_SIZE = 10
    total_valid = total_quarantine = 0

    for i in range(0, len(new_files), BATCH_SIZE):
        batch = new_files[i : i + BATCH_SIZE]
        raw_df = pd.concat([pd.read_parquet(f) for f in batch], ignore_index=True)

        valid_df, quarantine_df = validate_batch(raw_df)
        silver_df = enrich_silver(valid_df)

        # Append to Silver (real Databricks: Delta append — ACID, dedup via MERGE)
        SILVER_PATH.parent.mkdir(parents=True, exist_ok=True)
        if SILVER_PATH.exists():
            existing = pd.read_parquet(SILVER_PATH)
            combined = pd.concat([existing, silver_df], ignore_index=True)
        else:
            combined = silver_df
        combined.to_parquet(SILVER_PATH, index=False)

        # Write quarantine (real DLT: quarantine table with @expect_or_quarantine)
        if not quarantine_df.empty:
            q_path = SILVER_PATH.parent / "quarantine.parquet"
            if q_path.exists():
                qex = pd.concat([pd.read_parquet(q_path), quarantine_df], ignore_index=True)
            else:
                qex = quarantine_df
            qex.to_parquet(q_path, index=False)

        processed.update(str(f) for f in batch)
        total_valid      += len(silver_df)
        total_quarantine += len(quarantine_df)
        logger.info("  Micro-batch %d/%d: valid=%d  quarantine=%d",
                    i // BATCH_SIZE + 1, -(-len(new_files) // BATCH_SIZE),
                    len(silver_df), len(quarantine_df))

    save_checkpoint(processed)
    logger.info(
        "AutoLoader run complete: written=%d  quarantined=%d  checkpoint=%d files",
        total_valid, total_quarantine, len(processed),
    )

    # Sample quality stats
    if SILVER_PATH.exists():
        silver = pd.read_parquet(SILVER_PATH)
        logger.info("Silver table stats:")
        logger.info("  Total rows:    %d", len(silver))
        logger.info("  Plants:        %s", silver["plant_id"].nunique())
        logger.info("  Anomaly rate:  %.2f%%", silver["is_temp_anomaly"].mean() * 100)
        logger.info("  Date range:    %s → %s",
                    silver["ingest_date"].min(), silver["ingest_date"].max())


if __name__ == "__main__":
    run_autoloader()
