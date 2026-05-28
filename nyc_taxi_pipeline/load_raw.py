import pandas as pd
from sqlalchemy import create_engine

# Conexiunea la Postgres
engine = create_engine('postgresql://vlad:vlad123@localhost:5432/portfolio')

# Citim fișierul Parquet
print("Citim datele...")
df = pd.read_parquet('data/yellow_tripdata_2024-01.parquet')
print(f"Rânduri încărcate: {len(df)}")

# Curățăm numele coloanelor — lowercase
df.columns = df.columns.str.lower()

# Încărcăm în Postgres
print("Încărcăm în Postgres...")
df.to_sql(
    name='raw_taxi_trips',
    con=engine,
    schema='public',
    if_exists='replace',
    index=False,
    chunksize=10000
)

print("Gata! Datele sunt în Postgres.")