"""
Delta Storage Layer — SmartCity Environmental Analytics
=======================================================
Simulates the ADLS Gen2 + Delta Lake storage tier of the Azure production stack.

Azure storage architecture:
    ┌─────────────────────────────────────────────────────────────┐
    │                    ADLS Gen2 Account                        │
    │                                                             │
    │  Container: raw/       ← Bronze (append-only, Parquet)     │
    │  Container: processed/ ← Silver (Delta, partitioned)       │
    │  Container: analytics/ ← Gold   (Delta, ZORDER'd)          │
    │  Container: archive/   ← Cold tier (7-year retention)      │
    └─────────────────────────────────────────────────────────────┘

This module provides a unified storage interface that works locally
and could be swapped for Azure SDK (azure-storage-file-datalake) in production.

Cost optimisation implemented here:
    - Lifecycle policy: moves Bronze files to Cool tier after 30 days
    - Archive tier: data older than 1 year moved to Azure Archive ($0.002/GB/month)
    - Partitioning: reduces query scan cost in downstream Databricks jobs
"""
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

STORAGE_ROOT  = Path("data/smartcity")
LIFECYCLE_LOG = STORAGE_ROOT / "lifecycle_log.json"


class ADLSGen2StorageLayer:
    """
    Simulates ADLS Gen2 storage with lifecycle management.

    Real Azure SDK equivalent:
        from azure.storage.filedatalake import DataLakeServiceClient
        service = DataLakeServiceClient(
            account_url=f"https://{account}.dfs.core.windows.net",
            credential=DefaultAzureCredential()  # Managed Identity in production
        )
    """

    def __init__(self, root: Path = STORAGE_ROOT):
        self.root     = root
        self.log_path = root / "lifecycle_log.json"
        self.root.mkdir(parents=True, exist_ok=True)

    def _container_path(self, container: str, *parts: str) -> Path:
        """
        Resolve container + path to local equivalent.
        Real Azure: f"abfss://{container}@{account}.dfs.core.windows.net/{'/'.join(parts)}"
        """
        p = self.root / container
        for part in parts:
            p = p / part
        p.mkdir(parents=True, exist_ok=True)
        return p

    # ── Write operations ──────────────────────────────────────────────────────

    def write_bronze(self, df: pd.DataFrame, source: str) -> Path:
        """
        Write raw data to Bronze container (append-only, never overwrite).

        Real Azure:
            blob_client.upload_blob(
                data=df.to_parquet(),
                name=f"raw/{source}/{datetime.utcnow():%Y/%m/%d/%H%M%S}.parquet",
                overwrite=False  # append-only for audit compliance
            )
        Storage tier: Hot (ADLS Gen2 default)
        Lifecycle: → Cool after 30 days ($0.013/GB/month)
        """
        ts      = datetime.utcnow().strftime("%Y/%m/%d")
        folder  = self._container_path("raw", source, ts)
        fname   = f"{datetime.utcnow():%H%M%S}_{len(df)}_rows.parquet"
        path    = folder / fname
        df.to_parquet(path, index=False)
        logger.info("Bronze write: container=raw  path=%s  rows=%d", path.relative_to(self.root), len(df))
        return path

    def write_delta_table(
        self,
        df: pd.DataFrame,
        container: str,
        table_name: str,
        mode: str = "overwrite",
        partition_by: Optional[list[str]] = None,
    ) -> Path:
        """
        Write a Delta-format table (simulated as Parquet + transaction log).

        Real Databricks:
            df.write.format("delta")
              .mode(mode)
              .partitionBy(*partition_by)
              .saveAsTable(f"main.{container}.{table_name}")

        Delta on ADLS Gen2 writes:
            {table_path}/_delta_log/00000000000000000000.json   (transaction log)
            {table_path}/part-00000-xxx.parquet                 (data file)

        Storage tier: Hot (active data)
        Lifecycle: → Cool after 90 days, → Archive after 365 days
        """
        table_path = self._container_path(container, table_name)
        data_path  = table_path / "data.parquet"

        if mode == "append" and data_path.exists():
            existing = pd.read_parquet(data_path)
            df = pd.concat([existing, df], ignore_index=True)

        df.to_parquet(data_path, index=False)

        # Write simulated Delta transaction log
        log_dir  = table_path / "_delta_log"
        log_dir.mkdir(exist_ok=True)
        version  = len(list(log_dir.glob("*.json")))
        log_entry = {
            "commitInfo": {
                "version":      version,
                "timestamp":    int(datetime.utcnow().timestamp() * 1000),
                "operation":    mode.upper(),
                "operationParameters": {
                    "mode": mode,
                    "partitionBy": json.dumps(partition_by or []),
                },
                "numOutputRows": len(df),
                "numFiles":      1,
            }
        }
        (log_dir / f"{version:020d}.json").write_text(json.dumps(log_entry, indent=2))
        logger.info(
            "Delta write: container=%-12s  table=%-30s  mode=%-9s  rows=%d  version=%d",
            container, table_name, mode, len(df), version,
        )
        return data_path

    # ── Read operations ───────────────────────────────────────────────────────

    def read_table(self, container: str, table_name: str,
                   version: Optional[int] = None) -> pd.DataFrame:
        """
        Read a Delta table, optionally at a historical version.

        Real Databricks time travel:
            spark.read.format("delta").option("versionAsOf", version).load(path)
            # OR
            spark.table(f"main.{container}.{table_name} VERSION AS OF {version}")
        """
        table_path = self.root / container / table_name
        data_path  = table_path / "data.parquet"

        if version is not None:
            # Simulate time travel by reading transaction log
            log_files = sorted((table_path / "_delta_log").glob("*.json"))
            if version < len(log_files):
                logger.info("Time travel: reading version %d of %s.%s", version, container, table_name)
            # In real Delta, each version has its own data files; here we return current data
            # with a time-travel annotation

        if not data_path.exists():
            raise FileNotFoundError(f"Table not found: {container}.{table_name}")
        return pd.read_parquet(data_path)

    def table_history(self, container: str, table_name: str) -> pd.DataFrame:
        """DESCRIBE HISTORY table — shows all Delta commits."""
        log_dir = self.root / container / table_name / "_delta_log"
        if not log_dir.exists():
            return pd.DataFrame()
        entries = []
        for f in sorted(log_dir.glob("*.json")):
            data = json.loads(f.read_text())
            info = data.get("commitInfo", {})
            entries.append({
                "version":   info.get("version"),
                "timestamp": info.get("timestamp"),
                "operation": info.get("operation"),
                "rows":      info.get("numOutputRows"),
            })
        return pd.DataFrame(entries)

    # ── Lifecycle management ──────────────────────────────────────────────────

    def apply_lifecycle_policy(self) -> dict:
        """
        Simulate Azure Storage Lifecycle Management policy.

        Real Azure: configured as a JSON policy on the storage account:
        {
          "rules": [
            {"name": "move-bronze-to-cool",
             "type": "Lifecycle",
             "definition": {
               "filters": {"blobTypes": ["blockBlob"], "prefixMatch": ["raw/"]},
               "actions": {"baseBlob": {"tierToCool": {"daysAfterModificationGreaterThan": 30}}}
             }},
            {"name": "archive-old-data",
             "definition": {
               "filters": {"prefixMatch": ["raw/"]},
               "actions": {"baseBlob": {"tierToArchive": {"daysAfterModificationGreaterThan": 365}}}
             }}
          ]
        }

        Cost impact on SmartCity:
            50 stations × 30 days × 0.5 MB/day = 750 MB/month Bronze
            Hot tier:     $0.018/GB  → $0.014/month
            Cool tier:    $0.010/GB  → $0.0075/month  (save 42% after 30 days)
            Archive tier: $0.002/GB  → for data > 1 year (save 89%)
        """
        cutoff_cool    = datetime.utcnow() - timedelta(days=30)
        cutoff_archive = datetime.utcnow() - timedelta(days=365)
        moved_cool = moved_archive = 0

        for parquet_file in (self.root / "raw").rglob("*.parquet"):
            mtime = datetime.fromtimestamp(parquet_file.stat().st_mtime)
            if mtime < cutoff_archive:
                # Move to archive container (simulated: rename directory)
                archive_dir = self.root / "archive" / parquet_file.relative_to(self.root / "raw").parent
                archive_dir.mkdir(parents=True, exist_ok=True)
                parquet_file.rename(archive_dir / parquet_file.name)
                moved_archive += 1
            elif mtime < cutoff_cool:
                moved_cool += 1  # In real Azure: change blob access tier, no file move

        result = {
            "policy_applied_at": datetime.utcnow().isoformat(),
            "files_to_cool_tier": moved_cool,
            "files_to_archive": moved_archive,
        }
        self.log_path.write_text(json.dumps(result, indent=2))
        logger.info("Lifecycle policy: cool=%d files  archive=%d files", moved_cool, moved_archive)
        return result


def run() -> None:
    storage = ADLSGen2StorageLayer()

    # Load gold data produced by spark_transform.py
    gold_path = Path("data/smartcity/gold/daily_station_metrics.parquet")
    if not gold_path.exists():
        logger.error("Gold file not found. Run processing/spark_transform.py first.")
        return

    gold_df = pd.read_parquet(gold_path)

    # Write to Delta storage layer
    storage.write_delta_table(gold_df, "analytics", "daily_station_metrics", mode="overwrite")
    storage.write_delta_table(gold_df, "analytics", "daily_station_metrics_v2", mode="append",
                               partition_by=["zone"])

    # Demonstrate Delta history
    history = storage.table_history("analytics", "daily_station_metrics")
    logger.info("\nDelta table history:")
    logger.info("\n%s", history.to_string(index=False))

    # Apply lifecycle policy
    storage.apply_lifecycle_policy()
    logger.info("Storage layer demo complete.")


if __name__ == "__main__":
    run()
