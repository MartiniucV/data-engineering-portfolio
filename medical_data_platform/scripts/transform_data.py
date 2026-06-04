"""
MedInsight Analytics Platform - Silver Layer Transformation
Reads raw Parquet files, applies cleaning, validation, and business rules,
then writes to the silver/ layer.
"""

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from loguru import logger
from rich.console import Console
from rich.table import Table

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import Settings

console = Console()

VALID_STATUSES = {"completed", "cancelled", "no_show", "rescheduled"}
VALID_GENDERS = {"M", "F"}


class SilverTransformer:
    """Applies cleaning and enrichment to produce silver-layer datasets."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.bronze = settings.data.bronze_dir
        self.silver = settings.data.silver_dir

    def _read(self, name: str) -> pd.DataFrame:
        path = self.bronze / f"{name}.parquet"
        df = pd.read_parquet(path)
        logger.debug(f"Read {name}: {len(df):,} rows")
        return df

    def _write(self, df: pd.DataFrame, name: str) -> None:
        path = self.silver / f"{name}.parquet"
        table = pa.Table.from_pandas(df)
        pq.write_table(table, path, compression="snappy")
        logger.info(f"Silver: {name} ({len(df):,} rows) -> {path}")

    # ── Transformations ───────────────────────────────────────────────────────

    def transform_clinics(self) -> pd.DataFrame:
        df = self._read("clinics")
        df = df.drop_duplicates(subset="clinic_id")
        df["opening_date"] = pd.to_datetime(df["opening_date"])
        df["is_active"] = df["is_active"].fillna(True)
        df["_silver_loaded_at"] = datetime.utcnow()
        return df

    def transform_specialties(self) -> pd.DataFrame:
        df = self._read("specialties")
        df = df.drop_duplicates(subset="specialty_id")
        df["_silver_loaded_at"] = datetime.utcnow()
        return df

    def transform_services(self) -> pd.DataFrame:
        df = self._read("services")
        df = df.drop_duplicates(subset="service_id")
        df["base_price"] = pd.to_numeric(df["base_price"], errors="coerce")
        df = df[df["base_price"] > 0]
        df["profitability_margin"] = df["profitability_margin"].clip(0, 1)
        df["reimbursement_pct"] = df["reimbursement_pct"].clip(0, 1)
        df["_silver_loaded_at"] = datetime.utcnow()
        return df

    def transform_doctors(self) -> pd.DataFrame:
        df = self._read("doctors")
        df = df.drop_duplicates(subset="doctor_id")
        df["gender"] = df["gender"].where(df["gender"].isin(VALID_GENDERS), other="U")
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce").clip(1.0, 5.0)
        df["years_experience"] = df["years_experience"].clip(0, 50)
        df["hire_date"] = pd.to_datetime(df["hire_date"])
        df["consultation_price"] = pd.to_numeric(df["consultation_price"], errors="coerce").fillna(200)
        df["monthly_salary"] = pd.to_numeric(df["monthly_salary"], errors="coerce")
        # Derived
        df["seniority_band"] = pd.cut(
            df["years_experience"],
            bins=[0, 5, 10, 20, 50],
            labels=["Junior", "Mid", "Senior", "Principal"],
        ).astype(str)
        df["_silver_loaded_at"] = datetime.utcnow()
        return df

    def transform_patients(self) -> pd.DataFrame:
        df = self._read("patients")
        df = df.drop_duplicates(subset="patient_id")
        df["gender"] = df["gender"].where(df["gender"].isin(VALID_GENDERS), other="U")
        df["birth_date"] = pd.to_datetime(df["birth_date"])
        df["registration_date"] = pd.to_datetime(df["registration_date"])
        df["age"] = df["age"].clip(0, 120)
        df["risk_score"] = pd.to_numeric(df["risk_score"], errors="coerce").clip(0, 100).fillna(0)
        # Age bands
        df["age_band"] = pd.cut(
            df["age"],
            bins=[0, 18, 35, 50, 65, 120],
            labels=["0-18", "19-35", "36-50", "51-65", "65+"],
        ).astype(str)
        # Risk category
        df["risk_category"] = pd.cut(
            df["risk_score"],
            bins=[-1, 25, 50, 75, 101],
            labels=["Low", "Medium", "High", "Critical"],
        ).astype(str)
        df["_silver_loaded_at"] = datetime.utcnow()
        return df

    def transform_appointments(self) -> pd.DataFrame:
        df = self._read("appointments")
        df = df.drop_duplicates(subset="appointment_id")
        df["scheduled_at"] = pd.to_datetime(df["scheduled_at"])
        df["actual_start"] = pd.to_datetime(df["actual_start"], errors="coerce")
        df["actual_end"] = pd.to_datetime(df["actual_end"], errors="coerce")
        df = df[df["status"].isin(VALID_STATUSES)]
        df["actual_price"] = pd.to_numeric(df["actual_price"], errors="coerce").fillna(0).clip(lower=0)
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce").clip(1.0, 5.0)
        df["waiting_time_minutes"] = pd.to_numeric(df["waiting_time_minutes"], errors="coerce").clip(0, 300)

        # Derived time fields
        df["appointment_date"] = df["scheduled_at"].dt.date
        df["appointment_year"] = df["scheduled_at"].dt.year
        df["appointment_month"] = df["scheduled_at"].dt.month
        df["appointment_quarter"] = df["scheduled_at"].dt.quarter
        df["appointment_dow"] = df["scheduled_at"].dt.day_name()
        df["appointment_hour"] = df["scheduled_at"].dt.hour
        df["is_weekend"] = df["scheduled_at"].dt.dayofweek >= 5

        # Flag no-shows booked > 30 days in future
        df["_silver_loaded_at"] = datetime.utcnow()
        return df

    def transform_billing(self) -> pd.DataFrame:
        df = self._read("billing")
        df = df.drop_duplicates(subset="billing_id")
        df["invoice_date"] = pd.to_datetime(df["invoice_date"])
        for col in ["service_price", "discount_amount", "insurance_reimbursement",
                    "patient_paid", "tax_amount", "total_amount", "refund_amount"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).clip(lower=0)
        # Net revenue
        df["net_revenue"] = df["patient_paid"] - df["refund_amount"]
        df["net_revenue"] = df["net_revenue"].clip(lower=0)
        df["_silver_loaded_at"] = datetime.utcnow()
        return df

    def transform_prescriptions(self) -> pd.DataFrame:
        df = self._read("prescriptions")
        df = df.drop_duplicates(subset="prescription_id")
        df["prescribed_at"] = pd.to_datetime(df["prescribed_at"])
        df["duration_days"] = pd.to_numeric(df["duration_days"], errors="coerce").fillna(7).clip(1, 365)
        df["_silver_loaded_at"] = datetime.utcnow()
        return df

    def transform_lab_results(self) -> pd.DataFrame:
        df = self._read("lab_results")
        df = df.drop_duplicates(subset="lab_result_id")
        df["collected_at"] = pd.to_datetime(df["collected_at"])
        df["result_at"] = pd.to_datetime(df["result_at"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df["is_abnormal"] = df["is_abnormal"].fillna(False)
        # Turnaround time in hours
        df["turnaround_hours"] = (
            (df["result_at"] - df["collected_at"]).dt.total_seconds() / 3600
        ).clip(0, 200)
        df["_silver_loaded_at"] = datetime.utcnow()
        return df

    # ── Run ──────────────────────────────────────────────────────────────────

    def run(self) -> None:
        logger.info("Starting silver-layer transformation")

        transforms = {
            "clinics": self.transform_clinics,
            "specialties": self.transform_specialties,
            "services": self.transform_services,
            "doctors": self.transform_doctors,
            "patients": self.transform_patients,
            "appointments": self.transform_appointments,
            "billing": self.transform_billing,
            "prescriptions": self.transform_prescriptions,
            "lab_results": self.transform_lab_results,
        }

        results = {}
        for name, fn in transforms.items():
            logger.info(f"Transforming: {name}")
            df = fn()
            self._write(df, name)
            results[name] = len(df)

        tbl = Table(title="[bold green]Silver Layer Summary", header_style="bold magenta")
        tbl.add_column("Table", style="cyan")
        tbl.add_column("Rows", justify="right", style="green")
        for name, cnt in results.items():
            tbl.add_row(name, f"{cnt:,}")
        console.print(tbl)

        logger.success("Silver-layer transformation complete")


def main() -> None:
    settings = Settings()
    transformer = SilverTransformer(settings)
    transformer.run()


if __name__ == "__main__":
    main()
