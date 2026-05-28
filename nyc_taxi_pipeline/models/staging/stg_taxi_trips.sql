{{config(materialized='view')}}
SELECT
    vendorid,
    tpep_pickup_datetime AS pickup_datetime,
    tpep_dropoff_datetime AS dropoff_datetime,
    passenger_count,
    trip_distance,
    fare_amount,
    tip_amount,
    total_amount
    FROM {{ source('public', 'raw_taxi_trips') }}
WHERE tpep_pickup_datetime >= '2024-01-01'
AND tpep_pickup_datetime < '2024-02-01'