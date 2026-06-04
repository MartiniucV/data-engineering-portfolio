"""
MedInsight Analytics Platform - PostgreSQL Loader
Loads all generated datasets into PostgreSQL with proper schemas,
indexes, foreign keys, and materialized views.
"""

import io
import sys
import time
from pathlib import Path
from typing import Optional

import pandas as pd
from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import Settings

console = Console()


DDL_SCHEMAS = """
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS warehouse;
CREATE SCHEMA IF NOT EXISTS analytics;
"""

DDL_TABLES = """
-- ── raw.clinics ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw.clinics (
    clinic_id               VARCHAR(10)  PRIMARY KEY,
    name                    VARCHAR(150) NOT NULL,
    city                    VARCHAR(50)  NOT NULL,
    county                  VARCHAR(50),
    region                  VARCHAR(50),
    address                 VARCHAR(200),
    phone                   VARCHAR(30),
    capacity                INT,
    opening_date            DATE,
    specialization_focus    VARCHAR(100),
    operational_cost        NUMERIC(12,2),
    is_active               BOOLEAN DEFAULT TRUE,
    loaded_at               TIMESTAMPTZ DEFAULT NOW()
);

-- ── raw.specialties ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw.specialties (
    specialty_id            VARCHAR(10)  PRIMARY KEY,
    name                    VARCHAR(100) NOT NULL,
    avg_consultation_price  NUMERIC(10,2),
    avg_duration_min        INT,
    loaded_at               TIMESTAMPTZ DEFAULT NOW()
);

-- ── raw.services ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw.services (
    service_id              VARCHAR(10)  PRIMARY KEY,
    code                    VARCHAR(20)  NOT NULL UNIQUE,
    name                    VARCHAR(200) NOT NULL,
    category                VARCHAR(50),
    base_price              NUMERIC(10,2),
    duration_minutes        INT,
    profitability_margin    NUMERIC(5,4),
    reimbursement_pct       NUMERIC(5,4),
    is_active               BOOLEAN DEFAULT TRUE,
    loaded_at               TIMESTAMPTZ DEFAULT NOW()
);

-- ── raw.doctors ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw.doctors (
    doctor_id           VARCHAR(10)  PRIMARY KEY,
    first_name          VARCHAR(100) NOT NULL,
    last_name           VARCHAR(100) NOT NULL,
    full_name           VARCHAR(200),
    gender              CHAR(1),
    specialty           VARCHAR(100),
    clinic_id           VARCHAR(10)  REFERENCES raw.clinics(clinic_id),
    years_experience    INT,
    hire_date           DATE,
    consultation_price  NUMERIC(10,2),
    rating              NUMERIC(3,1),
    monthly_salary      NUMERIC(12,2),
    performance_score   NUMERIC(5,1),
    is_active           BOOLEAN DEFAULT TRUE,
    email               VARCHAR(200),
    phone               VARCHAR(30),
    burnout_risk_score  NUMERIC(5,1),
    loaded_at           TIMESTAMPTZ DEFAULT NOW()
);

-- ── raw.patients ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw.patients (
    patient_id          VARCHAR(10)  PRIMARY KEY,
    cnp                 VARCHAR(15),
    first_name          VARCHAR(100) NOT NULL,
    last_name           VARCHAR(100) NOT NULL,
    full_name           VARCHAR(200),
    gender              CHAR(1),
    birth_date          DATE,
    age                 INT,
    blood_type          VARCHAR(5),
    city                VARCHAR(50),
    county              VARCHAR(50),
    email               VARCHAR(200),
    phone               VARCHAR(30),
    insurance_status    VARCHAR(30),
    chronic_conditions  TEXT,
    risk_score          NUMERIC(5,1),
    registration_date   DATE,
    is_active           BOOLEAN DEFAULT TRUE,
    loaded_at           TIMESTAMPTZ DEFAULT NOW()
);

-- ── raw.appointments ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw.appointments (
    appointment_id                  VARCHAR(12) PRIMARY KEY,
    patient_id                      VARCHAR(10) REFERENCES raw.patients(patient_id),
    doctor_id                       VARCHAR(10) REFERENCES raw.doctors(doctor_id),
    service_id                      VARCHAR(10) REFERENCES raw.services(service_id),
    clinic_id                       VARCHAR(10) REFERENCES raw.clinics(clinic_id),
    specialty                       VARCHAR(100),
    scheduled_at                    TIMESTAMPTZ NOT NULL,
    actual_start                    TIMESTAMPTZ,
    actual_end                      TIMESTAMPTZ,
    status                          VARCHAR(20) NOT NULL,
    waiting_time_minutes            NUMERIC(8,1),
    consultation_duration_minutes   NUMERIC(8,1),
    channel                         VARCHAR(50),
    urgency_level                   VARCHAR(20),
    referral_source                 VARCHAR(100),
    cancellation_reason             VARCHAR(200),
    actual_price                    NUMERIC(10,2),
    discount_pct                    NUMERIC(5,4),
    rating                          NUMERIC(3,1),
    notes                           TEXT,
    loaded_at                       TIMESTAMPTZ DEFAULT NOW()
);

-- ── raw.billing ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw.billing (
    billing_id              VARCHAR(12)  PRIMARY KEY,
    appointment_id          VARCHAR(12)  REFERENCES raw.appointments(appointment_id),
    patient_id              VARCHAR(10)  REFERENCES raw.patients(patient_id),
    invoice_date            DATE         NOT NULL,
    service_price           NUMERIC(10,2),
    discount_amount         NUMERIC(10,2),
    insurance_reimbursement NUMERIC(10,2),
    patient_paid            NUMERIC(10,2),
    tax_amount              NUMERIC(10,2),
    total_amount            NUMERIC(10,2),
    refund_amount           NUMERIC(10,2),
    net_revenue             NUMERIC(10,2),
    payment_method          VARCHAR(50),
    payment_status          VARCHAR(30),
    insurance_type          VARCHAR(30),
    loaded_at               TIMESTAMPTZ DEFAULT NOW()
);

-- ── raw.prescriptions ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw.prescriptions (
    prescription_id VARCHAR(12)  PRIMARY KEY,
    appointment_id  VARCHAR(12)  REFERENCES raw.appointments(appointment_id),
    doctor_id       VARCHAR(10)  REFERENCES raw.doctors(doctor_id),
    patient_id      VARCHAR(10)  REFERENCES raw.patients(patient_id),
    medication_name VARCHAR(200),
    dosage          VARCHAR(50),
    frequency       VARCHAR(50),
    duration_days   INT,
    prescribed_at   TIMESTAMPTZ,
    is_chronic      BOOLEAN,
    loaded_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ── raw.lab_results ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw.lab_results (
    lab_result_id           VARCHAR(15)  PRIMARY KEY,
    appointment_id          VARCHAR(12)  REFERENCES raw.appointments(appointment_id),
    patient_id              VARCHAR(10)  REFERENCES raw.patients(patient_id),
    test_name               VARCHAR(100),
    value                   NUMERIC(12,3),
    unit                    VARCHAR(30),
    reference_range_low     NUMERIC(12,3),
    reference_range_high    NUMERIC(12,3),
    is_abnormal             BOOLEAN,
    collected_at            TIMESTAMPTZ,
    result_at               TIMESTAMPTZ,
    loaded_at               TIMESTAMPTZ DEFAULT NOW()
);
"""

DDL_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_appointments_patient   ON raw.appointments(patient_id);
CREATE INDEX IF NOT EXISTS idx_appointments_doctor    ON raw.appointments(doctor_id);
CREATE INDEX IF NOT EXISTS idx_appointments_clinic    ON raw.appointments(clinic_id);
CREATE INDEX IF NOT EXISTS idx_appointments_scheduled ON raw.appointments(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_appointments_status    ON raw.appointments(status);
CREATE INDEX IF NOT EXISTS idx_billing_appointment    ON raw.billing(appointment_id);
CREATE INDEX IF NOT EXISTS idx_billing_date           ON raw.billing(invoice_date);
CREATE INDEX IF NOT EXISTS idx_billing_status         ON raw.billing(payment_status);
CREATE INDEX IF NOT EXISTS idx_prescriptions_patient  ON raw.prescriptions(patient_id);
CREATE INDEX IF NOT EXISTS idx_prescriptions_doctor   ON raw.prescriptions(doctor_id);
CREATE INDEX IF NOT EXISTS idx_lab_results_patient    ON raw.lab_results(patient_id);
CREATE INDEX IF NOT EXISTS idx_lab_results_test       ON raw.lab_results(test_name);
CREATE INDEX IF NOT EXISTS idx_patients_city          ON raw.patients(city);
CREATE INDEX IF NOT EXISTS idx_patients_insurance     ON raw.patients(insurance_status);
CREATE INDEX IF NOT EXISTS idx_doctors_specialty      ON raw.doctors(specialty);
CREATE INDEX IF NOT EXISTS idx_doctors_clinic         ON raw.doctors(clinic_id);
"""

DDL_MATERIALIZED_VIEWS = """
-- Monthly revenue summary (analytics fast access)
CREATE MATERIALIZED VIEW IF NOT EXISTS analytics.mv_monthly_revenue AS
SELECT
    DATE_TRUNC('month', b.invoice_date)::DATE  AS month,
    c.city,
    d.specialty,
    COUNT(*)                                    AS num_invoices,
    SUM(b.total_amount)                         AS total_revenue,
    SUM(b.insurance_reimbursement)              AS total_reimbursement,
    AVG(b.total_amount)                         AS avg_invoice
FROM raw.billing b
JOIN raw.appointments a  ON b.appointment_id = a.appointment_id
JOIN raw.doctors d       ON a.doctor_id = d.doctor_id
JOIN raw.clinics c       ON a.clinic_id = c.clinic_id
GROUP BY 1, 2, 3
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS uidx_mv_monthly_revenue
    ON analytics.mv_monthly_revenue (month, city, specialty);

-- Doctor performance summary
CREATE MATERIALIZED VIEW IF NOT EXISTS analytics.mv_doctor_performance AS
SELECT
    d.doctor_id,
    d.full_name,
    d.specialty,
    d.clinic_id,
    COUNT(a.appointment_id)                                         AS total_appointments,
    COUNT(a.appointment_id) FILTER (WHERE a.status = 'completed')  AS completed,
    COUNT(a.appointment_id) FILTER (WHERE a.status = 'cancelled')  AS cancelled,
    COUNT(a.appointment_id) FILTER (WHERE a.status = 'no_show')    AS no_shows,
    ROUND(AVG(a.rating) FILTER (WHERE a.rating IS NOT NULL), 2)    AS avg_rating,
    ROUND(AVG(a.waiting_time_minutes)::NUMERIC, 1)                 AS avg_wait_min,
    COALESCE(SUM(b.total_amount), 0)                               AS total_revenue,
    d.performance_score
FROM raw.doctors d
LEFT JOIN raw.appointments a ON d.doctor_id = a.doctor_id
LEFT JOIN raw.billing b      ON a.appointment_id = b.appointment_id
GROUP BY d.doctor_id, d.full_name, d.specialty, d.clinic_id, d.performance_score
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS uidx_mv_doctor_perf ON analytics.mv_doctor_performance(doctor_id);
"""


class PostgresLoader:
    """Handles schema creation and data loading into PostgreSQL."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine = create_engine(settings.db.url, pool_pre_ping=True)
        self._configure_engine()

    def _configure_engine(self) -> None:
        @event.listens_for(self.engine, "connect")
        def set_search_path(dbapi_conn, conn_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("SET search_path TO raw, public")
            cursor.close()

    def _execute_ddl(self, ddl: str, label: str) -> None:
        with self.engine.begin() as conn:
            for stmt in ddl.split(";"):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(text(stmt))
        logger.info(f"DDL executed: {label}")

    def create_schemas(self) -> None:
        self._execute_ddl(DDL_SCHEMAS, "schemas")

    def _migrate_columns(self) -> None:
        """Idempotently add new columns introduced in the enterprise upgrade."""
        migrations = [
            "ALTER TABLE raw.clinics ADD COLUMN IF NOT EXISTS region VARCHAR(50)",
            "ALTER TABLE raw.clinics ADD COLUMN IF NOT EXISTS specialization_focus VARCHAR(100)",
            "ALTER TABLE raw.clinics ADD COLUMN IF NOT EXISTS operational_cost NUMERIC(12,2)",
            "ALTER TABLE raw.doctors ADD COLUMN IF NOT EXISTS burnout_risk_score NUMERIC(5,1)",
            "ALTER TABLE raw.billing ADD COLUMN IF NOT EXISTS net_revenue NUMERIC(10,2)",
        ]
        with self.engine.begin() as conn:
            for stmt in migrations:
                conn.execute(text(stmt))
        logger.info("Column migrations applied")

    def create_tables(self) -> None:
        self._execute_ddl(DDL_TABLES, "tables")
        self._migrate_columns()

    def create_indexes(self) -> None:
        self._execute_ddl(DDL_INDEXES, "indexes")

    def create_materialized_views(self) -> None:
        self._execute_ddl(DDL_MATERIALIZED_VIEWS, "materialized views")

    def _load_table_copy(self, df: pd.DataFrame, table_name: str, schema: str = "raw") -> int:
        """Bulk-load via PostgreSQL COPY — 10-50× faster than INSERT for large tables."""
        # Convert float columns whose values are all whole numbers (e.g. 25.0 → 25)
        # to pandas nullable Int64 so CSV writes "25" not "25.0", satisfying INT columns.
        df = df.copy()
        for col in df.select_dtypes(include="float64").columns:
            non_null = df[col].dropna()
            if len(non_null) > 0 and (non_null == non_null.astype("int64")).all():
                df[col] = df[col].astype("Int64")

        buf = io.StringIO()
        df.to_csv(buf, index=False, na_rep="")
        buf.seek(0)
        # Build explicit column list from CSV header (excludes DB-generated loaded_at)
        buf.seek(0)
        header_cols = buf.readline().strip().split(",")
        buf.seek(0)
        col_list = ", ".join(header_cols)

        raw_conn = self.engine.raw_connection()
        try:
            with raw_conn.cursor() as cur:
                cur.copy_expert(
                    f"COPY {schema}.{table_name} ({col_list}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE, NULL '')",
                    buf,
                )
            raw_conn.commit()
        finally:
            raw_conn.close()
        logger.debug(f"COPY loaded {len(df):,} rows into {schema}.{table_name}")
        return len(df)

    def _load_table(
        self,
        df: pd.DataFrame,
        table_name: str,
        schema: str = "raw",
        batch_size: int = 5000,
    ) -> int:
        """Chunked INSERT fallback for small tables."""
        total_rows = 0
        for i in range(0, len(df), batch_size):
            chunk = df.iloc[i : i + batch_size]
            chunk.to_sql(table_name, self.engine, schema=schema,
                         if_exists="append", index=False, method="multi")
            total_rows += len(chunk)
        logger.debug(f"Loaded {total_rows:,} rows into {schema}.{table_name}")
        return total_rows

    def _truncate_table(self, table_name: str, schema: str = "raw") -> None:
        with self.engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE {schema}.{table_name} CASCADE"))
        logger.debug(f"Truncated {schema}.{table_name}")

    def load_all(self) -> None:
        raw_dir = self.settings.data.raw_dir
        load_order = [
            "clinics", "specialties", "services", "doctors",
            "patients", "appointments", "billing", "prescriptions", "lab_results",
        ]

        results: dict[str, int] = {}

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(),
            TextColumn("[green]{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Loading into PostgreSQL", total=len(load_order))

            for table in load_order:
                path = raw_dir / f"{table}.csv"
                if not path.exists():
                    logger.warning(f"Missing CSV: {path} — skipping")
                    progress.advance(task)
                    continue

                progress.update(task, description=f"Loading {table}...")
                df = pd.read_csv(path, low_memory=False)
                self._truncate_table(table, schema="raw")
                # Use COPY for large tables, INSERT for small ones
                if len(df) > 10_000:
                    rows = self._load_table_copy(df, table, schema="raw")
                else:
                    rows = self._load_table(df, table, schema="raw")
                results[table] = rows
                progress.advance(task)

        table_display = Table(title="[bold green]PostgreSQL Load Summary", header_style="bold magenta")
        table_display.add_column("Table", style="cyan")
        table_display.add_column("Rows Loaded", justify="right", style="green")
        for tbl, cnt in results.items():
            table_display.add_row(f"raw.{tbl}", f"{cnt:,}")
        console.print(table_display)

    def refresh_materialized_views(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.mv_monthly_revenue"))
            conn.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.mv_doctor_performance"))
        logger.info("Materialized views refreshed")

    def run(self) -> None:
        logger.info("Starting PostgreSQL load process")
        self.create_schemas()
        self.create_tables()
        self.create_indexes()
        self.load_all()
        self.create_materialized_views()
        logger.success("PostgreSQL load complete")


def main() -> None:
    settings = Settings()
    loader = PostgresLoader(settings)
    loader.run()


if __name__ == "__main__":
    main()
