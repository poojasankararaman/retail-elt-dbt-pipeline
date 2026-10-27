-- Current-state customer dimension. Full history of moves lives in the
-- snapshots.customers_snapshot table (SCD Type 2).
with orders as (

    select
        customer_id,
        count(*) as lifetime_orders,
        sum(payment_total) as lifetime_revenue,
        min(purchased_at) as first_order_at,
        max(purchased_at) as last_order_at
    from {{ ref('fct_orders') }}
    where order_status <> 'canceled'
    group by 1

)

select
    c.customer_id,
    c.city,
    c.state,
    coalesce(o.lifetime_orders, 0) as lifetime_orders,
    coalesce(o.lifetime_revenue, 0) as lifetime_revenue,
    o.first_order_at,
    o.last_order_at
from {{ ref('stg_customers') }} c
left join orders o on o.customer_id = c.customer_id
