{{config(materialized='table')}}
SELECT
    date(pickup_datetime) AS trip_date,
    count(*) AS total_trips,
    sum(total_amount) AS total_revenue,
    avg(trip_distance) AS avg_distance,
    avg(tip_amount) AS avg_tip
FROM {{ ref('stg_taxi_trips') }}
GROUP BY trip_date