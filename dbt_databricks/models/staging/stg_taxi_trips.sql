{{
    config(
        materialized='view',
        -- On Databricks, views are stored in the Unity Catalog schema.
        -- dbt prepends the schema defined in profiles.yml automatically:
        --   main.nyc_taxi_dev.stg_taxi_trips
    )
}}

/*
Staging model: clean and standardise raw NYC Taxi trip records.

Key differences from the PostgreSQL version (nyc_taxi_pipeline/):
  - Reads from a Unity Catalog source table (three-level namespace)
  - Uses Databricks SQL functions (same ANSI SQL, but Photon-optimised)
  - The view is Delta-backed and query-accelerated by the SQL Warehouse
  - Schema changes upstream are handled by on_schema_change: merge (dbt_project.yml)

Source:
  main.raw.taxi_trips   (loaded via COPY INTO or Auto Loader on Databricks)

Filtering rules:
  - Valid year 2024 only (raw file has stray 2002 / 2009 records)
  - trip_distance, fare_amount, total_amount, passenger_count all > 0
  - dropoff must be after pickup
*/

with source as (

    select * from {{ source('raw', 'taxi_trips') }}

),

cleaned as (

    select
        -- ── Identifiers ─────────────────────────────────────────────────────
        vendorid                                            as vendor_id,
        ratecodeid                                          as rate_code_id,
        pulocationid                                        as pickup_location_id,
        dolocationid                                        as dropoff_location_id,

        -- ── Timestamps ──────────────────────────────────────────────────────
        tpep_pickup_datetime                                as pickup_datetime,
        tpep_dropoff_datetime                               as dropoff_datetime,
        date(tpep_pickup_datetime)                          as pickup_date,
        hour(tpep_pickup_datetime)                          as pickup_hour,

        -- ── Trip details ────────────────────────────────────────────────────
        cast(passenger_count as int)                        as passenger_count,
        trip_distance,
        store_and_fwd_flag,
        payment_type,

        -- ── Financials ──────────────────────────────────────────────────────
        fare_amount,
        extra,
        mta_tax,
        tip_amount,
        tolls_amount,
        improvement_surcharge,
        total_amount,

        -- ── Derived ─────────────────────────────────────────────────────────
        -- trip_duration_minutes: used downstream for speed and quality checks
        round(
            (
                unix_timestamp(tpep_dropoff_datetime)
                - unix_timestamp(tpep_pickup_datetime)
            ) / 60.0,
            2
        )                                                   as trip_duration_minutes

    from source

    where
        -- Valid year (source file has rows from 2002 and 2009)
        year(tpep_pickup_datetime)  = {{ var('start_date', '2024-01-01') | truncate(4, '') }}
        -- Physical constraints
        and trip_distance           > 0
        and fare_amount             > 0
        and total_amount            > 0
        and passenger_count         > 0
        -- Temporal integrity
        and tpep_pickup_datetime    is not null
        and tpep_dropoff_datetime   is not null
        and tpep_dropoff_datetime   > tpep_pickup_datetime
        -- Reasonable duration (> 1 min, < 6 hours)
        and (
            unix_timestamp(tpep_dropoff_datetime)
            - unix_timestamp(tpep_pickup_datetime)
        ) between 60 and 21600

)

select * from cleaned
