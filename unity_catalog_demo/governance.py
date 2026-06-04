"""
Unity Catalog Data Governance Demo

Demonstrates three governance patterns available natively in Databricks
Unity Catalog:

1. ROW-LEVEL SECURITY (RLS)
   Users see only the rows they're permitted to access, based on their group
   membership. On Databricks this is a Row Access Policy — a SQL function
   attached to the table that Databricks evaluates automatically on every query.

   -- Real Databricks SQL:
   CREATE ROW ACCESS POLICY region_policy
   AS (city STRING) RETURNS BOOLEAN
   RETURN CASE
     WHEN is_member('admins')     THEN TRUE
     WHEN is_member('eu_analysts') THEN city IN ('London')
     WHEN is_member('us_analysts') THEN city IN ('New York', 'Sydney')
     ELSE FALSE
   END;
   ALTER TABLE silver.clean_weather SET ROW FILTER region_policy ON (city);

2. COLUMN MASKING
   Sensitive columns are obfuscated at query time for non-privileged users.
   The original data is stored unmasked; the mask is applied by the engine.

   -- Real Databricks SQL:
   CREATE COLUMN MASK wind_mask
   AS (col DOUBLE) RETURNS DOUBLE
   RETURN CASE WHEN is_member('admins') THEN col ELSE -1.0 END;
   ALTER TABLE silver.clean_weather ALTER COLUMN wind_speed_kmh SET MASK wind_mask;

3. DATA TAGGING (Column classification)
   Columns are tagged with sensitivity labels (PII, GDPR, confidential).
   Tags drive downstream masking policies and compliance reports.

   -- Real Databricks SQL:
   ALTER TABLE silver.clean_weather ALTER COLUMN city
   SET TAGS ('pii' = 'true', 'classification' = 'internal');

This script simulates all three using Python + pandas so you can run it
without a live Databricks workspace.
"""
import logging

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

DIVIDER = "─" * 60

# ── Simulated user directory ───────────────────────────────────────────────────
# On Databricks groups are managed in Account Console → Identity & Access.
USER_GROUPS: dict[str, list[str]] = {
    "alice":   ["admins"],
    "bob":     ["eu_analysts"],
    "charlie": ["us_analysts"],
    "dave":    ["viewers"],
    "eve":     [],          # no groups → no access
}

# Which cities each group may see (RLS policy)
GROUP_CITY_ACCESS: dict[str, list[str]] = {
    "admins":      ["New York", "London", "Tokyo", "Sydney", "Sao Paulo"],
    "eu_analysts": ["London"],
    "us_analysts": ["New York", "Sydney"],
    "viewers":     [],  # no row access
}

# Column sensitivity tags
COLUMN_TAGS: dict[str, dict[str, str]] = {
    "city":             {"classification": "internal", "pii": "false"},
    "temperature_max":  {"classification": "public",   "pii": "false"},
    "temperature_min":  {"classification": "public",   "pii": "false"},
    "wind_speed_kmh":   {"classification": "confidential", "pii": "false"},
    "precipitation_mm": {"classification": "public",   "pii": "false"},
}

# Columns masked for non-admins
MASKED_COLUMNS = ["wind_speed_kmh"]

# ── Sample data ────────────────────────────────────────────────────────────────
RAW_DATA = pd.DataFrame([
    {"date": "2024-01-01", "city": "New York", "temperature_max": 8.5, "temperature_min": -2.3, "precipitation_mm": 0.0, "wind_speed_kmh": 15.2},
    {"date": "2024-01-01", "city": "London",   "temperature_max": 6.1, "temperature_min":  1.2, "precipitation_mm": 5.3, "wind_speed_kmh": 20.1},
    {"date": "2024-01-01", "city": "Tokyo",    "temperature_max":10.3, "temperature_min":  3.1, "precipitation_mm": 2.1, "wind_speed_kmh": 12.5},
    {"date": "2024-01-01", "city": "Sydney",   "temperature_max":22.4, "temperature_min": 14.1, "precipitation_mm": 0.0, "wind_speed_kmh":  8.3},
    {"date": "2024-01-02", "city": "New York", "temperature_max":10.1, "temperature_min": -1.2, "precipitation_mm": 2.5, "wind_speed_kmh": 18.3},
    {"date": "2024-01-02", "city": "London",   "temperature_max": 7.2, "temperature_min":  2.1, "precipitation_mm":10.1, "wind_speed_kmh": 22.4},
])


def apply_row_filter(df: pd.DataFrame, user: str) -> pd.DataFrame:
    """Simulate a Unity Catalog Row Access Policy."""
    groups      = USER_GROUPS.get(user, [])
    allowed     = set()
    for g in groups:
        allowed.update(GROUP_CITY_ACCESS.get(g, []))

    if "admins" in groups:
        return df  # admins bypass RLS

    return df[df["city"].isin(allowed)].copy()


def apply_column_mask(df: pd.DataFrame, user: str) -> pd.DataFrame:
    """Simulate a Unity Catalog Column Mask."""
    groups = USER_GROUPS.get(user, [])
    if "admins" in groups:
        return df  # admins see raw values

    result = df.copy()
    for col in MASKED_COLUMNS:
        if col in result.columns:
            result[col] = "*** MASKED ***"
    return result


def show_column_tags() -> None:
    """Print column classification tags — mirrors DESCRIBE EXTENDED in Databricks."""
    logger.info(DIVIDER)
    logger.info("  COLUMN TAGS (Unity Catalog metadata)")
    logger.info(DIVIDER)
    logger.info("  %-22s  %-14s  %s", "COLUMN", "CLASSIFICATION", "PII")
    for col, tags in COLUMN_TAGS.items():
        logger.info("  %-22s  %-14s  %s", col, tags["classification"], tags["pii"])


def demo_access(user: str) -> None:
    logger.info(DIVIDER)
    logger.info("  User: %-10s  Groups: %s", user, USER_GROUPS.get(user, []))
    logger.info(DIVIDER)

    after_rls    = apply_row_filter(RAW_DATA, user)
    after_mask   = apply_column_mask(after_rls, user)

    if after_mask.empty:
        logger.info("  Access denied — no rows visible (no region grant)")
        return

    logger.info("  Visible rows: %d / %d", len(after_mask), len(RAW_DATA))
    logger.info("\n%s", after_mask.to_string(index=False))


if __name__ == "__main__":
    show_column_tags()

    logger.info("")
    logger.info("=" * 60)
    logger.info("  ROW-LEVEL SECURITY + COLUMN MASKING DEMO")
    logger.info("=" * 60)

    for user in USER_GROUPS:
        demo_access(user)

    logger.info(DIVIDER)
    logger.info("  REAL DATABRICKS EQUIVALENT")
    logger.info(DIVIDER)
    logger.info("  -- Assign user to group:")
    logger.info("  GRANT USE CATALOG, USE SCHEMA ON CATALOG portfolio TO `eu_analysts`;")
    logger.info("  GRANT SELECT ON TABLE silver.clean_weather TO `eu_analysts`;")
    logger.info("  -- The Row Access Policy and Column Mask enforce the rest automatically.")
