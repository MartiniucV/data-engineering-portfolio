{{
    config(
        materialized='table',
        file_format='delta',
        -- OPTIMIZE + ZORDER runs automatically via post_hook in dbt_project.yml.
        -- ZORDER BY trip_date co-locates rows for the same date in the same Delta
        -- files, so WHERE trip_date = '...' queries skip irrelevant files entirely.
        -- On very large tables this reduces scan size by 90%+.
    )
}}

/*
Fact table: daily NYC Taxi trip metrics.

On Databricks this table is registered in Unity Catalog and can be queried:
  - Directly via Databricks SQL / SQL Warehouse
  - From Power BI / Tableau via the Databricks partner connector
  - From a Databricks notebook with spark.read.table("main.marts.fct_trips_daily")
  - Via the REST API by downstream ML pipelines

Grain: one row per calendar day (trip_date).

Key differences from PostgreSQL version (nyc_taxi_pipeline/):
  - Written as a Delta table (ACID, time travel, schema evolution)
  - ZORDER applied after write for data skipping on date filters
  - Photon engine processes the GROUP BY ~10x faster than standard Spark
*/

with trips as (

    select * from {{ ref('stg_taxi_trips') }}

),

daily_metrics as (

    select
        pickup_date                                                     as trip_date,

        -- ── Volume ─────────────────────────────────────────────────────────
        count(*)                                                        as total_trips,
        sum(passenger_count)                                            as total_passengers,

        -- ── Revenue ────────────────────────────────────────────────────────
        round(sum(total_amount),                           2)           as total_revenue,
        round(avg(fare_amount),                            2)           as avg_fare,
        round(sum(tip_amount),                             2)           as total_tips,
        round(
            avg(tip_amount / nullif(fare_amount, 0)),
        4)                                                              as avg_tip_rate,

        -- ── Efficiency ─────────────────────────────────────────────────────
        round(avg(trip_distance),                          2)           as avg_distance_miles,
        round(avg(trip_duration_minutes),                  2)           as avg_duration_minutes,
        round(
            avg(
                trip_distance
                / nullif(trip_duration_minutes / 60.0, 0)
            ),
        2)                                                              as avg_speed_mph,

        -- ── Payment mix ────────────────────────────────────────────────────
        -- payment_type: 1=Credit Card, 2=Cash, 3=No charge, 4=Dispute
        round(
            sum(case when payment_type = 1 then 1 else 0 end)
            / count(*) * 100,
        2)                                                              as credit_card_pct,

        -- ── Rush-hour breakdown ────────────────────────────────────────────
        sum(case when pickup_hour between 7  and 9  then 1 else 0 end) as morning_rush_trips,
        sum(case when pickup_hour between 17 and 19 then 1 else 0 end) as evening_rush_trips,

        -- ── Tip performance ────────────────────────────────────────────────
        round(max(tip_amount),                             2)           as max_tip,
        round(sum(total_amount) / count(*),                2)           as revenue_per_trip

    from trips

    group by trip_date

)

select * from daily_metrics
order by trip_date
