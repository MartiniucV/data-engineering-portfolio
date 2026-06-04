import pandas as pd
import shutil
import sys
from sqlalchemy import create_engine

DB = "postgresql://vlad:vlad123@host.docker.internal:5432/portfolio"

def bronze():
    shutil.copy(
        "/opt/medallion/data/yellow_tripdata_2024-01.parquet",
        "/opt/medallion/bronze/"
    )
    print("Bronze: fisier copiat")

def silver():
    engine = create_engine(DB)
    df = pd.read_parquet("/opt/medallion/bronze/yellow_tripdata_2024-01.parquet")
    df = df.head(100000)
    df.columns = df.columns.str.lower()
    df = df[
        (df["tpep_pickup_datetime"] >= "2024-01-01") &
        (df["tpep_pickup_datetime"] < "2024-02-01") &
        (df["trip_distance"] > 0) &
        (df["total_amount"] > 0)
    ]
    df.to_sql("silver_taxi_trips", engine, if_exists="replace", index=False, chunksize=5000)
    print(f"Silver: {len(df)} randuri salvate")

def gold():
    engine = create_engine(DB)
    with engine.connect() as con:
        con.execute("""
            CREATE OR REPLACE VIEW gold_trips_daily AS
            SELECT
                DATE(tpep_pickup_datetime) AS trip_date,
                COUNT(*) AS total_trips,
                SUM(total_amount) AS total_revenue,
                AVG(trip_distance) AS avg_distance,
                AVG(tip_amount) AS avg_tip
            FROM silver_taxi_trips
            GROUP BY trip_date
            ORDER BY trip_date
        """)
    print("Gold: view creat")

if __name__ == "__main__":
    step = sys.argv[1]
    if step == "bronze": bronze()
    elif step == "silver": silver()
    elif step == "gold": gold()
