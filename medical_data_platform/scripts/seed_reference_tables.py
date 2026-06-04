"""
MedInsight Analytics Platform - Reference Table Seeder
Seeds static lookup tables (calendar dimension, specialty codes, ICD-10 categories).
"""

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from loguru import logger
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import Settings


def generate_calendar(start: date, end: date) -> pd.DataFrame:
    """Generate a complete date dimension table."""
    rows = []
    current = start
    while current <= end:
        rows.append({
            "date_id": int(current.strftime("%Y%m%d")),
            "full_date": current,
            "year": current.year,
            "quarter": (current.month - 1) // 3 + 1,
            "month": current.month,
            "month_name": current.strftime("%B"),
            "month_name_ro": ["Ianuarie","Februarie","Martie","Aprilie","Mai","Iunie",
                               "Iulie","August","Septembrie","Octombrie","Noiembrie","Decembrie"][current.month - 1],
            "week": current.isocalendar()[1],
            "day_of_month": current.day,
            "day_of_week": current.isoweekday(),
            "day_name": current.strftime("%A"),
            "is_weekend": current.isoweekday() >= 6,
            "is_holiday": _is_romanian_holiday(current),
            "fiscal_year": current.year if current.month >= 1 else current.year - 1,
        })
        current += timedelta(days=1)
    return pd.DataFrame(rows)


def _is_romanian_holiday(d: date) -> bool:
    """Check if date is a Romanian national holiday."""
    holidays = {
        (1, 1), (1, 2),   # New Year
        (1, 24),           # Union Day
        (5, 1),            # Labour Day
        (6, 1),            # Children's Day
        (8, 15),           # Assumption
        (11, 30),          # St. Andrew
        (12, 1),           # National Day
        (12, 25), (12, 26) # Christmas
    }
    return (d.month, d.day) in holidays


def seed_tables(settings: Settings) -> None:
    engine = create_engine(settings.db.url, pool_pre_ping=True)

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS warehouse.dim_calendar (
                date_id         INT          PRIMARY KEY,
                full_date       DATE         NOT NULL,
                year            INT,
                quarter         INT,
                month           INT,
                month_name      VARCHAR(20),
                month_name_ro   VARCHAR(20),
                week            INT,
                day_of_month    INT,
                day_of_week     INT,
                day_name        VARCHAR(15),
                is_weekend      BOOLEAN,
                is_holiday      BOOLEAN,
                fiscal_year     INT
            )
        """))
        conn.execute(text("TRUNCATE TABLE warehouse.dim_calendar"))

    calendar = generate_calendar(date(2022, 1, 1), date(2025, 12, 31))
    calendar.to_sql("dim_calendar", engine, schema="warehouse", if_exists="append", index=False, method="multi")
    logger.info(f"Seeded dim_calendar: {len(calendar):,} rows")


def main() -> None:
    settings = Settings()
    seed_tables(settings)
    logger.success("Reference tables seeded")


if __name__ == "__main__":
    main()
