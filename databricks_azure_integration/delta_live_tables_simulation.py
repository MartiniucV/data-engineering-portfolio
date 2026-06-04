"""
Delta Live Tables (DLT) Simulation — ManufactureX Sensor Quality Pipeline
==========================================================================
Business Context:
    ManufactureX discovered that 8% of raw sensor readings are invalid
    (out-of-range values, null sensor IDs, corrupt timestamps).
    Bad data caused a false equipment-failure alert that triggered an
    emergency plant shutdown costing $180K.

    Solution: DLT pipeline with data quality expectations that quarantine
    bad records BEFORE they reach downstream ML anomaly detection models.

What is Delta Live Tables?
    DLT is Databricks' declarative pipeline framework. You declare WHAT
    you want (quality rules, transformations), not HOW to execute them.
    DLT handles: retry logic, checkpointing, schema evolution, lineage,
                 data quality metrics dashboard, incremental processing.

    Three expectation actions:
        @expect               — flag bad rows (metric only, no drop)
        @expect_or_drop       — remove bad rows from output
        @expect_or_fail       — fail the pipeline entirely on violation
        @expect_or_quarantine — route bad rows to a separate quarantine table (NEW in 2024)

This script simulates DLT decorator behaviour using a class-based registry,
so you can see exactly what DLT does without needing a Databricks cluster.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

SILVER_PATH     = Path("data/adls_simulation/sensor-data/silver/sensor_readings.parquet")
GOLD_PATH       = Path("data/dlt_simulation/gold")
QUARANTINE_PATH = Path("data/dlt_simulation/quarantine")
METRICS_PATH    = Path("data/dlt_simulation/quality_metrics.json")


# ── DLT Expectation simulation ─────────────────────────────────────────────────

class ExpectationAction(str):
    WARN      = "warn"       # @dlt.expect
    DROP      = "drop"       # @dlt.expect_or_drop
    FAIL      = "fail"       # @dlt.expect_or_fail
    QUARANTINE = "quarantine" # @dlt.expect_or_quarantine


@dataclass
class Expectation:
    """
    Simulates a DLT @dlt.expect decorator.

    Real DLT syntax:
        @dlt.expect("valid_temperature", "temperature_c BETWEEN -40 AND 200")
        @dlt.expect_or_drop("non_null_sensor", "sensor_id IS NOT NULL")
        @dlt.expect_or_fail("valid_plant", "plant_id IS NOT NULL")
        @dlt.expect_or_quarantine("valid_readings",
                                   "temperature_c BETWEEN -40 AND 200 AND sensor_id IS NOT NULL")
    """
    name:       str
    predicate:  Callable[[pd.DataFrame], pd.Series]  # returns bool mask (True = valid)
    action:     str = ExpectationAction.WARN
    description: str = ""

    def apply(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
        """
        Apply expectation. Returns (passing_df, failing_df, metrics).
        Real DLT: metrics stored in event_log Delta table, viewable in DLT UI.
        """
        mask        = self.predicate(df)
        passing     = df[mask].copy()
        failing     = df[~mask].copy()

        metrics = {
            "expectation_name":  self.name,
            "action":            self.action,
            "total_rows":        len(df),
            "passing_rows":      int(mask.sum()),
            "failing_rows":      int((~mask).sum()),
            "pass_rate_pct":     round(mask.mean() * 100, 3),
            "evaluated_at":      datetime.utcnow().isoformat(),
        }

        status = "✓ PASS" if metrics["failing_rows"] == 0 else f"⚠ {metrics['failing_rows']} VIOLATIONS"
        logger.info(
            "  [Expectation] %-40s  action=%-12s  pass=%.2f%%  violations=%d  %s",
            self.name, self.action,
            metrics["pass_rate_pct"], metrics["failing_rows"], status,
        )
        return passing, failing, metrics


# ── DLT Table registry ─────────────────────────────────────────────────────────

@dataclass
class DLTTable:
    """
    Simulates @dlt.table decorator.

    Real DLT:
        @dlt.table(
            name="silver_sensor_readings",
            comment="Validated IoT sensor readings from ManufactureX plants",
            table_properties={"quality": "silver", "pipelines.autoOptimize.managed": "true"},
        )
        def silver_sensor_readings():
            return dlt.read_stream("bronze_raw_sensors").filter(...)
    """
    name:         str
    compute_fn:   Callable
    expectations: list[Expectation] = field(default_factory=list)
    comment:      str = ""
    is_streaming: bool = False


class DLTPipeline:
    """Simulates a DLT pipeline with its table registry and event log."""

    def __init__(self, name: str):
        self.name       = name
        self.tables:    list[DLTTable] = []
        self.event_log: list[dict]     = []

    def table(self, table: DLTTable) -> None:
        self.tables.append(table)

    def run(self) -> dict[str, pd.DataFrame]:
        """
        Execute the DLT pipeline.
        Real DLT: orchestrated by Databricks; handles incremental processing,
        checkpointing, cluster management, and UI updates automatically.
        """
        logger.info("=" * 60)
        logger.info("  DLT Pipeline: %s", self.name)
        logger.info("=" * 60)
        results: dict[str, pd.DataFrame] = {}
        quarantine_frames: list[pd.DataFrame] = []

        for tbl in self.tables:
            logger.info("Processing table: %s", tbl.name)
            df = tbl.compute_fn(results)

            for exp in tbl.expectations:
                passing, failing, metrics = exp.apply(df)
                self.event_log.append(metrics)

                if exp.action == ExpectationAction.DROP:
                    df = passing
                elif exp.action == ExpectationAction.QUARANTINE:
                    failing["_quarantine_expectation"] = exp.name
                    failing["_quarantine_ts"]           = datetime.utcnow().isoformat()
                    quarantine_frames.append(failing)
                    df = passing
                elif exp.action == ExpectationAction.FAIL:
                    if len(failing) > 0:
                        raise RuntimeError(
                            f"DLT expectation '{exp.name}' violated: "
                            f"{len(failing)} rows failed. Pipeline halted."
                        )

            results[tbl.name] = df
            logger.info("  → %s: %d rows", tbl.name, len(df))

        # Write quarantine table
        if quarantine_frames:
            quarantine = pd.concat(quarantine_frames, ignore_index=True)
            QUARANTINE_PATH.mkdir(parents=True, exist_ok=True)
            quarantine.to_parquet(QUARANTINE_PATH / "sensor_quarantine.parquet", index=False)
            logger.info("Quarantine table: %d rows → %s", len(quarantine), QUARANTINE_PATH)

        return results

    def print_quality_report(self) -> None:
        """
        Print DLT quality metrics.
        Real DLT: visible in Pipelines UI → Data Quality tab,
        and queryable via event_log Delta table.
        """
        if not self.event_log:
            return
        logger.info("\n  DATA QUALITY REPORT")
        logger.info("  %-42s  %-12s  %8s  %10s", "EXPECTATION", "ACTION", "PASS%", "VIOLATIONS")
        logger.info("  " + "─" * 78)
        for e in self.event_log:
            logger.info(
                "  %-42s  %-12s  %7.3f%%  %10d",
                e["expectation_name"], e["action"],
                e["pass_rate_pct"], e["failing_rows"],
            )
        total_violations = sum(e["failing_rows"] for e in self.event_log)
        logger.info("  " + "─" * 78)
        logger.info("  Total violations: %d", total_violations)


# ── Pipeline definition ────────────────────────────────────────────────────────

def load_bronze(results: dict) -> pd.DataFrame:
    """
    Bronze: read from AutoLoader-written Silver file (simulating DLT streaming source).
    Real DLT: dlt.read_stream("bronze_raw_sensors") reads new Delta records
    since last checkpoint — exactly-once, incremental.
    """
    if not SILVER_PATH.exists():
        logger.warning("Silver file not found. Run medallion_with_autoloader.py first.")
        # Generate synthetic data for standalone testing
        np.random.seed(42)
        n = 5_000
        return pd.DataFrame({
            "sensor_id":    [f"P01-MCH-{i % 20:03d}-SEN" for i in range(n)],
            "machine_id":   [f"P01-MCH-{i % 20:03d}" for i in range(n)],
            "plant_id":     np.random.choice(["PLANT-01", "PLANT-02", "PLANT-03"], n),
            "timestamp":    pd.date_range("2024-01-01", periods=n, freq="30s"),
            "temperature_c": np.random.normal(75, 10, n),
            "vibration_hz": np.random.uniform(0.1, 12, n),
            "pressure_bar": np.random.uniform(1, 8, n),
            "humidity_pct": np.random.uniform(30, 80, n),
            "power_kw":     np.random.uniform(2, 45, n),
            "is_anomaly":   np.random.choice([True, False], n, p=[0.05, 0.95]),
        })
    return pd.read_parquet(SILVER_PATH)


def transform_silver_validated(results: dict) -> pd.DataFrame:
    """Validated silver — passed through DLT expectations."""
    return results.get("bronze_raw", load_bronze(results))


def compute_gold_plant_health(results: dict) -> pd.DataFrame:
    """
    Gold: hourly plant health KPIs.
    Real DLT: this table is auto-OPTIMIZE'd, Z-ORDERED, and registered in UC.
    Power BI connects directly for real-time plant monitoring dashboards.
    """
    df = results.get("silver_validated", pd.DataFrame())
    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["hour"]      = df["timestamp"].dt.floor("h")

    return (
        df.groupby(["plant_id", "hour"])
        .agg(
            total_readings=("sensor_id", "count"),
            avg_temperature=("temperature_c", "mean"),
            max_temperature=("temperature_c", "max"),
            avg_vibration=("vibration_hz", "mean"),
            max_vibration=("vibration_hz", "max"),
            avg_power_kw=("power_kw", "mean"),
            anomaly_count=("is_anomaly", "sum"),
        )
        .round(3)
        .reset_index()
        .assign(anomaly_rate=lambda x: (x["anomaly_count"] / x["total_readings"] * 100).round(3))
    )


def build_dlt_pipeline() -> DLTPipeline:
    pipeline = DLTPipeline("manufacturex_iot_pipeline")

    # Table 1: Bronze (raw — no quality checks, just land the data)
    pipeline.table(DLTTable(
        name="bronze_raw",
        compute_fn=load_bronze,
        comment="Raw IoT sensor readings from ManufactureX ADLS Gen2 landing zone",
    ))

    # Table 2: Silver (validated — expectations applied)
    pipeline.table(DLTTable(
        name="silver_validated",
        compute_fn=transform_silver_validated,
        comment="Validated sensor readings — invalid records quarantined",
        expectations=[
            Expectation(
                "non_null_sensor_id",
                lambda df: df["sensor_id"].notna(),
                action=ExpectationAction.DROP,
                description="Sensor ID must be present",
            ),
            Expectation(
                "valid_temperature_range",
                lambda df: df["temperature_c"].between(-40, 220),
                action=ExpectationAction.QUARANTINE,
                description="Temperature must be between -40°C and 220°C",
            ),
            Expectation(
                "valid_pressure_range",
                lambda df: df["pressure_bar"].between(0, 25),
                action=ExpectationAction.QUARANTINE,
                description="Pressure must be between 0 and 25 bar",
            ),
            Expectation(
                "non_negative_vibration",
                lambda df: df["vibration_hz"] >= 0,
                action=ExpectationAction.WARN,
                description="Vibration must be non-negative",
            ),
            Expectation(
                "valid_plant_id",
                lambda df: df["plant_id"].str.startswith("PLANT-", na=False),
                action=ExpectationAction.FAIL,   # hard stop — plant misconfiguration
                description="Plant ID must start with 'PLANT-'",
            ),
        ],
    ))

    # Table 3: Gold (aggregated plant health)
    pipeline.table(DLTTable(
        name="gold_plant_health_hourly",
        compute_fn=compute_gold_plant_health,
        comment="Hourly plant KPIs — feeds real-time monitoring dashboard",
    ))

    return pipeline


def run() -> None:
    pipeline  = build_dlt_pipeline()
    results   = pipeline.run()
    pipeline.print_quality_report()

    GOLD_PATH.mkdir(parents=True, exist_ok=True)
    if "gold_plant_health_hourly" in results and not results["gold_plant_health_hourly"].empty:
        gold = results["gold_plant_health_hourly"]
        gold.to_parquet(GOLD_PATH / "plant_health.parquet", index=False)
        logger.info("\nGold table sample (top 5 rows by anomaly rate):")
        logger.info("\n%s", gold.nlargest(5, "anomaly_rate").to_string(index=False))

    import json
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(json.dumps(pipeline.event_log, indent=2))
    logger.info("\nQuality metrics → %s", METRICS_PATH)


if __name__ == "__main__":
    run()
