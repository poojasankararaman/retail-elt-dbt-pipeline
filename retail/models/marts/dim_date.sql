-- Date spine built with a recursive CTE so it is portable across DuckDB and Snowflake
-- and needs no external dbt packages.
with recursive bounds as (

    select
        cast(min(purchased_at) as date) as first_day,
        cast(max(purchased_at) as date) as last_day
    from {{ ref('stg_orders') }}

),

spine as (

    select first_day as date_day, last_day from bounds

    union all

    select
        cast({{ dbt.dateadd('day', 1, 'date_day') }} as date) as date_day,
        last_day
    from spine
    where date_day < last_day

)

select
    date_day,
    extract(year from date_day) as year,
    extract(quarter from date_day) as quarter,
    extract(month from date_day) as month,
    cast({{ dbt.date_trunc('month', 'date_day') }} as date) as month_start
from spine
