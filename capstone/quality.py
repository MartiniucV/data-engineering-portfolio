"""
Data quality checks for the weather pipeline.

Runs a suite of assertions against the PostgreSQL table loaded by transform.py.
Exits with code 1 if any check fails so the script can be wired into a CI step
or an Airflow task with fail_on_violation=True.
"""
import logging
import sys
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

DB_URL = "postgresql://vlad:vlad123@localhost:5432/portfolio"
TABLE = "weather_daily"
EXPECTED_CITIES = {"New York", "London", "Tokyo", "Sydney", "Sao Paulo"}


@dataclass
class CheckResult:
    description: str
    passed: bool
    details: Optional[str] = None


@dataclass
class QualityReport:
    results: list[CheckResult] = field(default_factory=list)

    def add(self, description: str, condition: bool, details: Optional[str] = None) -> None:
        r = CheckResult(description, condition, details)
        self.results.append(r)
        status = "PASS" if condition else "FAIL"
        msg = f"[{status}] {description}"
        if details:
            msg += f"  ({details})"
        (logger.info if condition else logger.error)(msg)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    def summary(self) -> str:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        return f"{passed}/{total} checks passed"


def run_checks() -> QualityReport:
    engine = create_engine(DB_URL)
    df = pd.read_sql(f"SELECT * FROM {TABLE}", engine)
    df["date"] = pd.to_datetime(df["date"])

    report = QualityReport()
    logger.info("Running quality checks on %d rows in '%s'...", len(df), TABLE)

    # ── Volume ────────────────────────────────────────────────────────────────
    report.add("Table is non-empty",       len(df) > 0,    f"{len(df)} rows")
    report.add("At least 100 rows loaded", len(df) >= 100, f"{len(df)} rows")

    # ── Completeness ──────────────────────────────────────────────────────────
    for col in ["date", "city", "temperature_2m_max", "temperature_2m_min"]:
        nulls = int(df[col].isna().sum())
        report.add(f"No NULLs in '{col}'", nulls == 0, f"{nulls} nulls")

    # ── City coverage ─────────────────────────────────────────────────────────
    found = set(df["city"].unique())
    missing = EXPECTED_CITIES - found
    report.add(
        "All expected cities present",
        not missing,
        f"missing: {missing}" if missing else None,
    )

    # ── Temperature bounds ────────────────────────────────────────────────────
    in_range_max = df["temperature_2m_max"].between(-80, 60)
    report.add(
        "Max temperature in [-80, 60] °C",
        bool(in_range_max.all()),
        f"{(~in_range_max).sum()} violations",
    )
    in_range_min = df["temperature_2m_min"].between(-80, 60)
    report.add(
        "Min temperature in [-80, 60] °C",
        bool(in_range_min.all()),
        f"{(~in_range_min).sum()} violations",
    )
    max_gte_min = df["temperature_2m_max"] >= df["temperature_2m_min"]
    report.add(
        "Max temp >= min temp for all rows",
        bool(max_gte_min.all()),
        f"{(~max_gte_min).sum()} violations",
    )

    # ── Non-negative quantities ───────────────────────────────────────────────
    report.add(
        "Precipitation >= 0",
        bool((df["precipitation_sum"] >= 0).all()),
    )
    report.add(
        "Wind speed >= 0",
        bool((df["wind_speed_10m_max"] >= 0).all()),
    )

    # ── Uniqueness ────────────────────────────────────────────────────────────
    dupes = int(df.duplicated(subset=["date", "city"]).sum())
    report.add("No duplicate (date, city) pairs", dupes == 0, f"{dupes} duplicates")

    # ── Date range ────────────────────────────────────────────────────────────
    span = int((df["date"].max() - df["date"].min()).days)
    report.add("Date span >= 30 days", span >= 30, f"{span} days")

    # ── Derived column consistency ────────────────────────────────────────────
    expected_range = (df["temperature_2m_max"] - df["temperature_2m_min"]).round(6)
    actual_range = df["temp_range"].round(6)
    mismatch = int((expected_range != actual_range).sum())
    report.add(
        "temp_range == max_temp - min_temp",
        mismatch == 0,
        f"{mismatch} mismatches",
    )

    logger.info("─" * 50)
    logger.info("Quality check complete: %s", report.summary())
    return report


if __name__ == "__main__":
    report = run_checks()
    if not report.passed:
        sys.exit(1)
