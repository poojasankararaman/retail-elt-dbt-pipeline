-- Reporting mart: one row per day with orders and revenue (cancelled orders excluded).
select
    d.date_day,
    d.month_start,
    count(f.order_id) as orders,
    coalesce(sum(f.payment_total), 0) as revenue,
    coalesce(avg(f.payment_total), 0) as avg_order_value,
    avg(f.delivery_days) as avg_delivery_days
from {{ ref('dim_date') }} d
left join {{ ref('fct_orders') }} f
    on f.purchase_date = d.date_day
    and f.order_status <> 'canceled'
group by 1, 2
