"""
ADLS Gen2 Mount Pattern — ManufactureX IoT Pipeline
====================================================
Business Problem:
    ManufactureX, an industrial manufacturer, runs 10,000 factory sensors
    across 12 plants. Sensors emit readings every 30 seconds → 28.8M records/day.
    Data lands on ADLS Gen2; Databricks clusters need a consistent path
    abstraction so code works identically in dev, staging, and production.

What this simulates:
    Real Databricks (Spark)          Local Python equivalent
    ────────────────────────────     ─────────────────────────────────
    dbutils.fs.mount(...)            StorageMount class (path abstraction)
    ADLS Gen2 storage account        local filesystem under data/
    Managed Identity auth            env-var based config (no creds in code)
    dbutils.secrets.get(...)         os.environ.get(...) with fallback
    spark.read.parquet("abfss://")   pd.read_parquet(local_path)

Key Databricks patterns demonstrated:
    1. Mount abstraction — write code once, works on all environments
    2. Unity Catalog external location (preferred over mounts in UC workspaces)
    3. Service principal + Managed Identity authentication patterns
    4. Secret scope configuration
"""
import logging
import os
import shutil
import uuid
from dataclasses import dataclass, field
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


# ── Storage configuration ─────────────────────────────────────────────────────
# Real Databricks: these come from a secret scope backed by Azure Key Vault
# dbutils.secrets.get(scope="kv-scope", key="adls-account-name")
# Never hard-code credentials — use Managed Identity where possible.
STORAGE_ACCOUNT  = os.getenv("ADLS_ACCOUNT",   "manufacturex-datalake")
CONTAINER        = os.getenv("ADLS_CONTAINER",  "sensor-data")

# abfss:// URI format: abfss://{container}@{account}.dfs.core.windows.net/{path}
# Locally we map this to data/adls_simulation/{container}/
LOCAL_ADLS_ROOT  = Path("data/adls_simulation")


@dataclass
class StorageMount:
    """
    Abstraction over ADLS Gen2 storage paths.

    Real Databricks equivalent:
        # Legacy mount (still common in Unity Catalog-free workspaces):
        dbutils.fs.mount(
            source      = "abfss://sensor-data@manufacturex.dfs.core.windows.net/",
            mount_point = "/mnt/sensor-data",
            extra_configs = {
                "fs.azure.account.auth.type": "OAuth",
                "fs.azure.account.oauth.provider.type":
                    "org.apache.hadoop.fs.azurebfs.oauth2.ClientCredsTokenProvider",
                "fs.azure.account.oauth2.client.id":     client_id,
                "fs.azure.account.oauth2.client.secret": client_secret,
                "fs.azure.account.oauth2.client.endpoint": f"https://login.microsoftonline.com/{tenant_id}/oauth2/token",
            }
        )

        # Modern Unity Catalog approach (no mount needed):
        spark.read.parquet("abfss://sensor-data@manufacturex.dfs.core.windows.net/raw/")
        # OR register as External Location in UC → access like a regular table path
    """
    account:    str
    container:  str
    local_root: Path = field(default_factory=lambda: LOCAL_ADLS_ROOT)

    @property
    def mount_point(self) -> str:
        """Databricks mount point: /mnt/{container}"""
        return f"/mnt/{self.container}"

    @property
    def abfss_uri(self) -> str:
        """Real ADLS Gen2 URI used in Databricks."""
        return f"abfss://{self.container}@{self.account}.dfs.core.windows.net"

    def path(self, *parts: str) -> Path:
        """
        Resolve a logical path to a local filesystem path.

        Usage:
            mount.path("raw", "plant-01", "2024-01-15")
            # Returns: data/adls_simulation/sensor-data/raw/plant-01/2024-01-15

        Real Databricks:
            f"/mnt/{self.container}/raw/plant-01/2024-01-15"
            or
            f"abfss://sensor-data@manufacturex.dfs.core.windows.net/raw/plant-01/2024-01-15"
        """
        p = self.local_root / self.container
        for part in parts:
            p = p / part
        p.mkdir(parents=True, exist_ok=True)
        return p

    def list_files(self, *parts: str, pattern: str = "*.parquet") -> list[Path]:
        """
        List files at a path. Real Databricks: dbutils.fs.ls("/mnt/...")
        or spark.read.parquet(path) with wildcard auto-discovery.
        """
        folder = self.path(*parts)
        return sorted(folder.glob(pattern))

    def __repr__(self) -> str:
        return (
            f"StorageMount(account={self.account!r}, "
            f"container={self.container!r}, "
            f"abfss={self.abfss_uri!r})"
        )


# ── Sensor data generator (simulates ADLS raw landing zone) ──────────────────

PLANT_IDS    = [f"PLANT-{i:02d}" for i in range(1, 13)]
MACHINE_TYPES = ["CNC_Lathe", "Hydraulic_Press", "Conveyor_Belt", "Welding_Robot", "Assembly_Arm"]


def generate_sensor_batch(
    plant_id: str,
    machines_per_plant: int = 20,
    readings_per_machine: int = 50,
) -> pd.DataFrame:
    """
    Generate one batch of IoT sensor readings for a plant.
    Real ManufactureX: data arrives as gzip Parquet files on ADLS Gen2
    written by Azure IoT Hub → Stream Analytics → ADLS Gen2 route.
    """
    machine_ids = [f"{plant_id}-MCH-{i:03d}" for i in range(1, machines_per_plant + 1)]
    records     = []

    for mid in machine_ids:
        base_temp = np.random.uniform(60, 95)
        for _ in range(readings_per_machine):
            records.append({
                "sensor_id":        f"{mid}-SEN",
                "machine_id":       mid,
                "plant_id":         plant_id,
                "machine_type":     np.random.choice(MACHINE_TYPES),
                "timestamp":        fake_ts(),
                "temperature_c":    round(base_temp + np.random.normal(0, 3), 2),
                "vibration_hz":     round(np.random.uniform(0.1, 12.0), 3),
                "pressure_bar":     round(np.random.uniform(1.0, 8.5), 3),
                "humidity_pct":     round(np.random.uniform(30, 80), 1),
                "power_kw":         round(np.random.uniform(2.5, 45.0), 2),
                # Inject anomalies (5% of readings — basis for DLT expectations)
                "is_anomaly":       np.random.random() < 0.05,
                "batch_id":         str(uuid.uuid4())[:8],
            })

    return pd.DataFrame(records)


def fake_ts() -> str:
    """Generate a realistic recent timestamp."""
    delta_seconds = np.random.randint(0, 86400 * 7)  # last 7 days
    ts = datetime.utcnow() - __import__("datetime").timedelta(seconds=int(delta_seconds))
    return ts.isoformat()


# ── Mount operations ──────────────────────────────────────────────────────────

def simulate_data_landing(mount: StorageMount, num_plants: int = 3) -> list[Path]:
    """
    Simulate ADLS Gen2 raw data landing zone.
    Real ManufactureX: Azure IoT Hub routes messages to ADLS Gen2 via
    Message Routing → Storage endpoint.
    Files partition pattern: raw/{plant_id}/{date}/readings_{timestamp}.parquet
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    written: list[Path] = []

    for plant in PLANT_IDS[:num_plants]:
        df       = generate_sensor_batch(plant)
        filename = f"readings_{datetime.utcnow().strftime('%H%M%S')}.parquet"
        dest     = mount.path("raw", plant, today) / filename
        df.to_parquet(dest, index=False)
        written.append(dest)
        logger.info("  Landed: %-40s  (%d rows)", str(dest)[-55:], len(df))

    return written


def demonstrate_mount_patterns(mount: StorageMount) -> None:
    """
    Show how mount paths translate to Databricks and Azure SDK code.
    This is the kind of explanation you'd give in a Databricks interview.
    """
    logger.info("=== MOUNT POINT PATTERNS ===")
    logger.info("  Mount point (Databricks): %s", mount.mount_point)
    logger.info("  ADLS Gen2 URI:            %s", mount.abfss_uri)
    logger.info("  Local simulation root:    %s", mount.local_root)

    logger.info("\n  -- Reading in Databricks Notebook:")
    logger.info("  df = spark.read.parquet('/mnt/%s/raw/PLANT-01/2024-01-15/')", mount.container)
    logger.info("  # OR with Unity Catalog External Location (preferred):")
    logger.info("  df = spark.read.parquet('%s/raw/PLANT-01/2024-01-15/')", mount.abfss_uri)

    logger.info("\n  -- Writing in Databricks:")
    logger.info("  df.write.format('delta').save('/mnt/%s/silver/sensor_readings/')", mount.container)

    # List files in the raw landing zone
    all_files = []
    for plant in PLANT_IDS[:3]:
        all_files.extend(mount.list_files("raw", plant, "*"))

    logger.info("\n  Raw files landed: %d Parquet files", len(all_files))
    for f in all_files[:5]:
        size_kb = f.stat().st_size / 1024
        logger.info("    %-55s  (%.1f KB)", str(f)[-55:], size_kb)

    # Cost note
    logger.info("\n  Cost note: 10,000 sensors × 2 readings/min × 365 days")
    logger.info("  ≈ 10.5B rows/year ≈ 2 TB compressed on ADLS Gen2")
    logger.info("  ADLS Gen2 storage: ~$40/month | Databricks reads: ~$0.006/GB")


def run() -> None:
    mount = StorageMount(account=STORAGE_ACCOUNT, container=CONTAINER)
    logger.info("Simulating ADLS Gen2 mount: %s", mount)

    logger.info("Simulating IoT data landing (3 plants)...")
    simulate_data_landing(mount, num_plants=3)

    demonstrate_mount_patterns(mount)
    logger.info("mount_adls.py complete. See medallion_with_autoloader.py for ingestion.")


if __name__ == "__main__":
    run()
