{{
    config(
        materialized='incremental',
        unique_key='order_id',
        on_schema_change='sync_all_columns'
    )
}}

-- Grain: one row per order.
-- Incremental on _loaded_at: only orders (re)loaded since the last run are rebuilt,
-- and `unique_key` makes the merge idempotent (re-running never double counts).
--
-- Trade-off (documented on purpose): item/payment rows that arrive in a LATER batch
-- than their order will not update that order until the order itself is reloaded.
-- Fix options: widen the incremental window (lookback), or key the filter on the
-- max(_loaded_at) across orders, items and payments.

with orders as (

    select * from {{ ref('stg_orders') }}
    {% if is_incremental() %}
    where _loaded_at > (select max(_loaded_at) from {{ this }})
    {% endif %}

),

items as (

    select
        order_id,
        count(*) as item_count,
        sum(price) as items_total,
        sum(freight_value) as freight_total
    from {{ ref('stg_order_items') }}
    group by 1

),

payments as (

    select
        order_id,
        sum(payment_value) as payment_total
    from {{ ref('stg_payments') }}
    group by 1

)

select
    o.order_id,
    o.customer_id,
    cast(o.purchased_at as date) as purchase_date,
    o.purchased_at,
    o.delivered_at,
    o.order_status,
    o.order_status = 'delivered' as is_delivered,
    o.has_invalid_delivery_ts,
    coalesce(i.item_count, 0) as item_count,
    coalesce(i.items_total, 0) as items_total,
    coalesce(i.freight_total, 0) as freight_total,
    coalesce(p.payment_total, 0) as payment_total,
    case
        when o.delivered_at is not null
            then {{ dbt.datediff('o.purchased_at', 'o.delivered_at', 'day') }}
    end as delivery_days,
    o._loaded_at
from orders o
left join items i on i.order_id = o.order_id
left join payments p on p.order_id = o.order_id
