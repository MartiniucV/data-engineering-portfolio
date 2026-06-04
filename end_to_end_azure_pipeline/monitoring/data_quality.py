"""
Data Quality Monitoring — SmartCity Environmental Analytics
===========================================================
Azure Production: Great Expectations runs as a Databricks notebook task
or Azure Function after each pipeline run. Results written to ADLS Gen2
and surfaced in Azure Data Catalog / Purview as quality scores.

Great Expectations concepts demonstrated:
    - Expectation Suite: named collection of expectations
    - Checkpoint: ties a suite to a datasource + validation action
    - ValidationResult: pass/fail with statistics for each expectation
    - DataDocs: auto-generated HTML report (simulated here as logs)

Interview talking point: "Why not just write assert statements?"
    GE advantages: versioned suites, history tracking, integration with
    Azure Purview for data quality scoring, Slack/Teams alerts built-in,
    expectation gallery with 50+ ready-to-use checks.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

GOLD_PATH       = Path("data/smartcity/gold/daily_station_metrics.parquet")
QUALITY_RESULTS = Path("data/smartcity/monitoring/quality_results.json")

EXPECTED_STATIONS = {
    "CITY-CENTRE", "NORTH-SUBURBS", "INDUSTRIAL",
    "PARK-ZONE", "AIRPORT-PROX", "SOUTH-GATE",
    "RIVER-THAMES", "EAST-END",
}


# ── Lightweight GE-style expectation framework ────────────────────────────────

class ExpectationResult:
    def __init__(self, name: str, success: bool, observed: Any,
                 expected: str = "", details: str = ""):
        self.name     = name
        self.success  = success
        self.observed = observed
        self.expected = expected
        self.details  = details

    def to_dict(self) -> dict:
        return {
            "expectation":  self.name,
            "success":      self.success,
            "observed":     str(self.observed),
            "expected":     self.expected,
            "details":      self.details,
        }


class ExpectationSuite:
    """
    Mirrors great_expectations.core.ExpectationSuite.
    Real GE: suite stored as JSON in great_expectations/expectations/ directory.
    """
    def __init__(self, name: str):
        self.name    = name
        self.results: list[ExpectationResult] = []

    def expect(self, name: str, condition: bool, observed: Any,
               expected: str = "", details: str = "") -> bool:
        r = ExpectationResult(name, condition, observed, expected, details)
        self.results.append(r)
        icon = "✓" if condition else "✗"
        logger.info("  [%s] %-55s  observed=%s", icon, name, str(observed)[:40])
        return condition

    @property
    def passed(self) -> bool:
        return all(r.success for r in self.results)

    @property
    def pass_rate(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.success) / len(self.results) * 100

    def summary(self) -> dict:
        total  = len(self.results)
        passed = sum(1 for r in self.results if r.success)
        return {
            "suite_name":    self.name,
            "validated_at":  datetime.utcnow().isoformat(),
            "total_checks":  total,
            "passed_checks": passed,
            "failed_checks": total - passed,
            "pass_rate_pct": round(self.pass_rate, 2),
            "overall_status": "PASS" if self.passed else "FAIL",
            "results":       [r.to_dict() for r in self.results],
        }


# ── Expectation suites ────────────────────────────────────────────────────────

def suite_completeness(df: pd.DataFrame, suite: ExpectationSuite) -> None:
    """
    expect_column_values_to_not_be_null equivalents.
    Real GE:
        suite.expect_column_values_to_not_be_null("station_id")
        suite.expect_column_values_to_not_be_null("measurement_date")
        suite.expect_column_values_to_not_be_null("avg_aqi")
    """
    for col in ["station_id", "measurement_date", "avg_aqi", "max_temp", "min_temp"]:
        null_pct = df[col].isna().mean() * 100 if col in df.columns else 100.0
        suite.expect(
            f"expect_column_values_to_not_be_null({col})",
            null_pct == 0,
            f"{null_pct:.2f}% nulls",
            expected="0% nulls",
        )


def suite_volume(df: pd.DataFrame, suite: ExpectationSuite) -> None:
    """
    expect_table_row_count_to_be_between equivalent.
    Real GE: suite.expect_table_row_count_to_be_between(min_value=50, max_value=10000)
    """
    suite.expect("expect_table_row_count_to_be_between",
                 len(df) >= 50, len(df),
                 expected=">= 50 rows")

    suite.expect("expect_table_row_count_to_not_exceed",
                 len(df) <= 100_000, len(df),
                 expected="<= 100,000 rows")


def suite_station_coverage(df: pd.DataFrame, suite: ExpectationSuite) -> None:
    """
    expect_column_values_to_be_in_set equivalent.
    Real GE: suite.expect_column_values_to_be_in_set("station_id", expected_stations)
    """
    found   = set(df["station_id"].unique()) if "station_id" in df.columns else set()
    missing = EXPECTED_STATIONS - found
    suite.expect(
        "expect_all_stations_present",
        len(missing) == 0,
        f"found={len(found)}/{len(EXPECTED_STATIONS)}",
        expected=f"all {len(EXPECTED_STATIONS)} stations",
        details=f"missing: {missing}" if missing else "",
    )


def suite_value_ranges(df: pd.DataFrame, suite: ExpectationSuite) -> None:
    """
    expect_column_values_to_be_between equivalents.
    Real GE:
        suite.expect_column_values_to_be_between("avg_aqi", 0, 500)
        suite.expect_column_values_to_be_between("max_temp", -30, 55)
    """
    checks = [
        ("avg_aqi",    0,    500,  "AQI must be 0–500"),
        ("max_aqi",    0,    500,  "Max AQI must be 0–500"),
        ("max_temp",  -30,    55,  "Max temperature -30°C to 55°C"),
        ("min_temp",  -40,    40,  "Min temperature -40°C to 40°C"),
        ("max_wind",    0,   200,  "Wind speed 0–200 km/h"),
    ]
    for col, lo, hi, desc in checks:
        if col not in df.columns:
            continue
        out_of_range = (~df[col].between(lo, hi)).sum()
        suite.expect(
            f"expect_column_values_to_be_between({col}, {lo}, {hi})",
            out_of_range == 0,
            f"{out_of_range} violations",
            expected=f"all values in [{lo}, {hi}]",
            details=desc,
        )


def suite_statistical(df: pd.DataFrame, suite: ExpectationSuite) -> None:
    """
    expect_column_mean_to_be_between (statistical profiling).
    Real GE: combine with a Data Assistant to auto-generate these from historical runs.
    """
    if "avg_aqi" in df.columns:
        mean_aqi = df["avg_aqi"].mean()
        suite.expect(
            "expect_column_mean_aqi_to_be_between(10, 200)",
            10 <= mean_aqi <= 200,
            f"{mean_aqi:.1f}",
            expected="10–200 (typical urban AQI range)",
        )

    if "max_temp" in df.columns and "min_temp" in df.columns:
        invalid_order = (df["max_temp"] < df["min_temp"]).sum()
        suite.expect(
            "expect_max_temp_gte_min_temp",
            invalid_order == 0,
            f"{invalid_order} rows",
            expected="max_temp >= min_temp for all rows",
        )


def suite_freshness(df: pd.DataFrame, suite: ExpectationSuite) -> None:
    """
    Custom freshness check — data must be recent.
    Real GE: use expect_column_max_to_be_between on the date column.
    Azure Monitor: custom metric alert if freshness check fails.
    """
    if "measurement_date" not in df.columns:
        return
    dates  = pd.to_datetime(df["measurement_date"], errors="coerce")
    latest = dates.max()
    today  = pd.Timestamp.today().normalize()
    delta_days = (today - latest).days if pd.notna(latest) else 9999

    suite.expect(
        "expect_data_to_be_fresh_within_7_days",
        delta_days <= 7,
        f"latest={latest.date() if pd.notna(latest) else 'None'} ({delta_days}d ago)",
        expected="data within last 7 days",
    )


def run_quality_suite() -> dict:
    """
    Run all expectation suites and return the combined report.

    Real Azure:
        1. GE Checkpoint runs after Databricks spark_transform job completes
        2. ValidationResult written to ADLS Gen2 as JSON
        3. DataDocs HTML pushed to Azure Blob Static Website
        4. Azure Monitor custom metric: quality_pass_rate updated
        5. If pass_rate < 95%: Azure Alert fires → Teams notification
    """
    if not GOLD_PATH.exists():
        logger.error("Gold file not found at %s — run spark_transform.py first", GOLD_PATH)
        return {"error": "Gold file not found"}

    df = pd.read_parquet(GOLD_PATH)
    logger.info("Running GE-style quality suite on %d rows...", len(df))

    suite = ExpectationSuite("smartcity_daily_station_metrics_v1")

    suite_completeness(df, suite)
    suite_volume(df, suite)
    suite_station_coverage(df, suite)
    suite_value_ranges(df, suite)
    suite_statistical(df, suite)
    suite_freshness(df, suite)

    result = suite.summary()
    QUALITY_RESULTS.parent.mkdir(parents=True, exist_ok=True)
    QUALITY_RESULTS.write_text(json.dumps(result, indent=2))

    logger.info("─" * 60)
    logger.info("Quality suite: %s  pass_rate=%.1f%%  status=%s",
                suite.name, result["pass_rate_pct"], result["overall_status"])
    logger.info("Results → %s", QUALITY_RESULTS)

    if not suite.passed:
        failed = [r["expectation"] for r in result["results"] if not r["success"]]
        logger.warning("Failed expectations: %s", failed)

    return result


if __name__ == "__main__":
    run_quality_suite()
