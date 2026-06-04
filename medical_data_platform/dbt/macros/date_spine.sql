{% macro medinsight_date_spine(start_date, end_date) %}

with date_spine as (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('" ~ start_date ~ "' as date)",
        end_date="cast('" ~ end_date ~ "' as date)"
    ) }}
)

select
    date_day                                                        as full_date,
    extract(year  from date_day)::integer                           as year,
    extract(month from date_day)::integer                           as month,
    extract(quarter from date_day)::integer                         as quarter,
    to_char(date_day, 'YYYY-MM')                                    as year_month,
    extract(isodow from date_day)::integer                          as day_of_week,
    extract(isodow from date_day) >= 6                              as is_weekend
from date_spine

{% endmacro %}
