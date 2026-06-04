"""
Microsoft Fabric Lakehouse Simulation — RetailCo E-Commerce Analytics
======================================================================
Business Problem:
    RetailCo, a UK fashion retailer with 200 stores and 2M customers, is
    migrating from an on-premises SQL Server DWH to Microsoft Fabric to:
      - Cut infrastructure costs by ~60% (estimated)
      - Enable near-real-time analytics (< 1 hour latency vs 24-hour batch)
      - Give business analysts self-service access via Power BI DirectLake

What this script simulates locally:
    Component           Local Equivalent
    ─────────────────── ─────────────────────────────────────────────
    OneLake             data/onelake/  (filesystem root)
    Lakehouse Files/    data/onelake/.../Files/bronze/  (raw Parquet)
    Lakehouse Tables/   data/onelake/.../Tables/  (managed via DuckDB)
    SQL Analytics EP    DuckDB connection  (T-SQL-compatible queries)
    Fabric Notebook     see notebooks/ directory
    Power BI DirectLake gold.fct_revenue_daily  (aggregated for BI)

Wow factor: DuckDB's SQL Analytics Endpoint emulation — you can run
full T-SQL-compatible analytics on 200K orders in ~100ms locally,
exactly as a Fabric SQL Warehouse would on hundreds of millions of rows.
"""
import logging
import random
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from faker import Faker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

Faker.seed(42)
np.random.seed(42)
random.seed(42)
fake = Faker("en_GB")

# ── OneLake directory hierarchy ───────────────────────────────────────────────
# Real Fabric path: OneLake/{WorkspaceName}/{LakehouseName}.Lakehouse/
# Files/ = unmanaged raw data (Parquet, CSV, JSON)
# Tables/ = managed Delta tables, auto-registered in the Metastore
ONELAKE_ROOT = Path("data/onelake/RetailCo.Lakehouse")
BRONZE_PATH  = ONELAKE_ROOT / "Files/bronze"   # unmanaged — no auto-table
SILVER_PATH  = ONELAKE_ROOT / "Tables/silver"  # managed Delta table
GOLD_PATH    = ONELAKE_ROOT / "Tables/gold"    # managed Delta table

# Simulates the SQL Analytics Endpoint (T-SQL read access to all Tables/)
DB_PATH = "data/retailco_lakehouse.duckdb"

CATEGORIES  = ["Tops", "Bottoms", "Outerwear", "Footwear", "Accessories", "Sportswear"]
PAYMENT_OPS = ["credit_card", "debit_card", "paypal", "apple_pay", "gift_card"]
REGIONS     = ["London", "Manchester", "Birmingham", "Leeds", "Glasgow", "Edinburgh", "Bristol"]
LOYALTY     = ["Bronze", "Silver", "Gold", "Platinum"]
CHANNELS    = ["online", "in-store", "mobile_app"]


# ─── DATA GENERATION ──────────────────────────────────────────────────────────

def generate_products(n: int = 200) -> pd.DataFrame:
    """
    Product catalogue.
    Real Fabric: loaded via COPY INTO from Azure Blob Storage, or
    mirrored from Azure SQL Database using Fabric Mirroring (zero-ETL).
    """
    categories = np.random.choice(CATEGORIES, n)
    cost        = np.random.uniform(5, 150, n)
    return pd.DataFrame({
        "product_id":  [f"PROD-{i:05d}" for i in range(1, n + 1)],
        "name":        [f"{c} Style {i}" for i, c in enumerate(categories, 1)],
        "category":    categories,
        "cost_price":  cost.round(2),
        "base_price":  (cost * np.random.uniform(2.0, 3.5, n)).round(2),
        "active":      np.random.choice([True, False], n, p=[0.95, 0.05]),
    })


def generate_customers(n: int = 10_000) -> pd.DataFrame:
    """
    Customer master data.
    Real Fabric: synced from CRM (Dynamics 365) via Fabric Mirroring —
    changes reflect in OneLake within minutes, no ETL pipeline needed.
    """
    return pd.DataFrame({
        "customer_id":         [f"CUST-{i:07d}" for i in range(1, n + 1)],
        "email":               [fake.email() for _ in range(n)],
        "region":              np.random.choice(REGIONS, n),
        "loyalty_tier":        np.random.choice(LOYALTY, n, p=[0.40, 0.35, 0.18, 0.07]),
        "registration_date":   [
            fake.date_between(start_date="-5y", end_date="today") for _ in range(n)
        ],
        "is_email_subscribed": np.random.choice([True, False], n, p=[0.72, 0.28]),
    })


def generate_orders(products: pd.DataFrame, customers: pd.DataFrame, n: int = 200_000) -> pd.DataFrame:
    """
    Transactional order fact table (200K rows ≈ 1 month of RetailCo data).
    Real Fabric: streamed from the e-commerce platform via Fabric Eventstream
    (built on Azure Event Hubs) → Lakehouse destination connector.
    Latency from event to queryable row: ~30 seconds.
    """
    prods    = products.sample(n=n, replace=True).reset_index(drop=True)
    qty      = np.random.choice([1, 2, 3, 4, 5], n, p=[0.55, 0.25, 0.12, 0.05, 0.03])
    disc     = np.random.choice([0, 0.10, 0.20, 0.30, 0.50], n, p=[0.60, 0.15, 0.12, 0.08, 0.05])
    price    = prods["base_price"].values
    total    = (price * qty * (1 - disc)).round(2)

    return pd.DataFrame({
        "order_id":       [f"ORD-{i:09d}" for i in range(1, n + 1)],
        "customer_id":    np.random.choice(customers["customer_id"], n),
        "product_id":     prods["product_id"].values,
        "order_datetime": [
            fake.date_time_between(start_date="-1y", end_date="now") for _ in range(n)
        ],
        "quantity":       qty,
        "unit_price":     price,
        "discount_pct":   disc,
        "total_amount":   total,
        "channel":        np.random.choice(CHANNELS, n, p=[0.45, 0.40, 0.15]),
        "payment_method": np.random.choice(PAYMENT_OPS, n),
        "status": np.random.choice(
            ["completed", "returned", "cancelled", "pending"],
            n, p=[0.88, 0.07, 0.03, 0.02],
        ),
        "store_id": [
            f"STORE-{random.randint(1, 200):03d}" if random.random() > 0.45 else None
            for _ in range(n)
        ],
    })


# ─── BRONZE: raw landing zone ─────────────────────────────────────────────────

def ingest_bronze(orders: pd.DataFrame, products: pd.DataFrame, customers: pd.DataFrame) -> None:
    """
    Write raw data to the Lakehouse Files/ section as Parquet.

    Real Fabric:
      - Files land here via Data Pipeline Copy Activity or Eventstream
      - Files/ section = unmanaged (no automatic Delta table or schema)
      - Shortcut: create a Fabric Shortcut pointing to this path to expose
        it as a read-only table from another Lakehouse or ADLS Gen2 account
    """
    BRONZE_PATH.mkdir(parents=True, exist_ok=True)
    orders.to_parquet(BRONZE_PATH / "orders.parquet",    index=False)
    products.to_parquet(BRONZE_PATH / "products.parquet", index=False)
    customers.to_parquet(BRONZE_PATH / "customers.parquet", index=False)
    logger.info("Bronze → Files/: orders=%d  products=%d  customers=%d",
                len(orders), len(products), len(customers))


# ─── SILVER: validated + enriched ────────────────────────────────────────────

def transform_silver(con: duckdb.DuckDBPyConnection) -> None:
    """
    Join, clean and enrich data. Result stored in Tables/ section.

    Real Fabric:
      - Written as a Delta table to Tables/silver/orders
      - Auto-registered in the Lakehouse Metastore (no CREATE TABLE needed)
      - Immediately visible in the SQL Analytics Endpoint and Power BI
      - Can run this transformation in a Fabric Notebook (PySpark or pandas)
        or as a Fabric Data Pipeline Dataflow Gen2 activity

    Cost note:
      - Fabric capacity is consumed per CU-second of Spark/DuckDB compute
      - Storing 200K orders in Delta ≈ $0.02/month in OneLake (ADLS pricing)
    """
    bp = str(BRONZE_PATH)
    con.execute(f"""
        CREATE OR REPLACE TABLE silver.orders AS
        SELECT
            o.order_id,
            o.customer_id,
            o.product_id,
            CAST(o.order_datetime AS TIMESTAMP)                         AS order_datetime,
            CAST(o.order_datetime AS DATE)                              AS order_date,
            DATE_PART('year',  o.order_datetime)                        AS order_year,
            DATE_PART('month', o.order_datetime)                        AS order_month,
            DATE_PART('dow',   o.order_datetime)                        AS day_of_week,
            o.quantity,
            o.unit_price,
            o.discount_pct,
            o.total_amount,
            o.channel,
            o.payment_method,
            o.status,
            o.store_id,
            -- Enrichment: product dimension (avoids repeated joins in Gold)
            p.category                                                  AS product_category,
            p.base_price,
            p.cost_price,
            ROUND((o.unit_price - p.cost_price) * o.quantity, 2)       AS gross_margin,
            -- Enrichment: customer dimension
            c.region                                                    AS customer_region,
            c.loyalty_tier,
            -- Business flags
            (o.status = 'completed')                                    AS is_completed,
            (o.channel = 'online' OR o.channel = 'mobile_app')         AS is_digital,
            CURRENT_TIMESTAMP                                           AS _silver_ts
        FROM read_parquet('{bp}/orders.parquet') o
        LEFT JOIN read_parquet('{bp}/products.parquet')  p USING (product_id)
        LEFT JOIN read_parquet('{bp}/customers.parquet') c USING (customer_id)
        WHERE o.status   != 'cancelled'
          AND o.total_amount > 0
    """)
    count = con.execute("SELECT COUNT(*) FROM silver.orders").fetchone()[0]
    logger.info("Silver → Tables/: orders = %d rows", count)


# ─── GOLD: BI-ready aggregates ────────────────────────────────────────────────

def aggregate_gold(con: duckdb.DuckDBPyConnection) -> None:
    """
    Pre-aggregate to business grain. These tables power Power BI reports.

    Real Fabric — Power BI DirectLake mode:
      - Power BI reads Delta Parquet files from OneLake DIRECTLY
      - No data import, no cached copy — reads the actual Delta files
      - Sub-second refresh on tables with billions of rows
      - This is Fabric's biggest differentiator vs. traditional Import mode

    Cost note: DirectLake = zero query cost (reads storage, not compute)
    """
    con.execute("""
        CREATE OR REPLACE TABLE gold.fct_revenue_daily AS
        SELECT
            order_date,
            order_year,
            order_month,
            product_category,
            customer_region,
            channel,
            COUNT(*)                                                    AS total_orders,
            SUM(quantity)                                               AS total_units,
            ROUND(SUM(total_amount), 2)                                 AS gross_revenue,
            ROUND(SUM(gross_margin), 2)                                 AS total_margin,
            ROUND(SUM(gross_margin) / NULLIF(SUM(total_amount), 0) * 100, 2) AS margin_pct,
            ROUND(AVG(total_amount), 2)                                 AS avg_order_value,
            SUM(CASE WHEN is_digital THEN 1 ELSE 0 END)                AS digital_orders
        FROM silver.orders
        WHERE is_completed
        GROUP BY order_date, order_year, order_month,
                 product_category, customer_region, channel
    """)

    # Customer LTV — feeds the "high-value customer" segment in Power BI
    con.execute("""
        CREATE OR REPLACE TABLE gold.dim_customer_ltv AS
        SELECT
            customer_id,
            customer_region,
            loyalty_tier,
            COUNT(*)                                    AS total_orders,
            SUM(quantity)                               AS total_units_bought,
            ROUND(SUM(total_amount), 2)                 AS lifetime_value,
            ROUND(AVG(total_amount), 2)                 AS avg_order_value,
            MIN(order_date)                             AS first_order_date,
            MAX(order_date)                             AS last_order_date,
            DATE_DIFF('day', MIN(order_date), MAX(order_date)) AS tenure_days
        FROM silver.orders
        WHERE is_completed
        GROUP BY customer_id, customer_region, loyalty_tier
    """)

    r = con.execute("SELECT COUNT(*) FROM gold.fct_revenue_daily").fetchone()[0]
    c = con.execute("SELECT COUNT(*) FROM gold.dim_customer_ltv").fetchone()[0]
    logger.info("Gold → Tables/: fct_revenue_daily=%d  dim_customer_ltv=%d", r, c)


def show_insights(con: duckdb.DuckDBPyConnection) -> None:
    """Sample queries — equivalent to Power BI measures on a DirectLake model."""
    for title, sql in [
        ("TOP CATEGORIES BY REVENUE (£M)",
         "SELECT product_category, ROUND(SUM(gross_revenue)/1e6,2) AS rev_M, "
         "ROUND(SUM(total_margin)/1e6,2) AS margin_M FROM gold.fct_revenue_daily "
         "GROUP BY product_category ORDER BY rev_M DESC LIMIT 5"),

        ("REVENUE BY CHANNEL",
         "SELECT channel, SUM(total_orders) AS orders, "
         "ROUND(SUM(gross_revenue)/1e6,2) AS rev_M FROM gold.fct_revenue_daily "
         "GROUP BY channel ORDER BY rev_M DESC"),

        ("AVERAGE LTV BY LOYALTY TIER",
         "SELECT loyalty_tier, COUNT(*) AS customers, "
         "ROUND(AVG(lifetime_value),2) AS avg_ltv, "
         "ROUND(AVG(total_orders),1) AS avg_orders "
         "FROM gold.dim_customer_ltv GROUP BY loyalty_tier ORDER BY avg_ltv DESC"),
    ]:
        logger.info("=== %s ===", title)
        logger.info("\n%s", con.execute(sql).df().to_string(index=False))


def run() -> None:
    Path("data").mkdir(exist_ok=True)

    logger.info("Generating RetailCo e-commerce dataset (200K orders)...")
    products  = generate_products(200)
    customers = generate_customers(10_000)
    orders    = generate_orders(products, customers, 200_000)

    ingest_bronze(orders, products, customers)

    # DuckDB = local SQL Analytics Endpoint
    (SILVER_PATH.parent).mkdir(parents=True, exist_ok=True)
    (GOLD_PATH.parent).mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(DB_PATH)
    con.execute("CREATE SCHEMA IF NOT EXISTS silver")
    con.execute("CREATE SCHEMA IF NOT EXISTS gold")

    transform_silver(con)
    aggregate_gold(con)
    show_insights(con)
    con.close()

    logger.info("Done. DuckDB SQL endpoint: %s", DB_PATH)
    logger.info("Run Jupyter notebooks in notebooks/ for interactive exploration.")


if __name__ == "__main__":
    run()
