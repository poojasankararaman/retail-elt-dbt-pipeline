-- Reconciliation: revenue in the reporting mart must equal revenue in the fact table
-- (cancelled orders excluded in both). Catches join fan-out and date-spine gaps.
with fact as (
    select sum(payment_total) as total
    from {{ ref('fct_orders') }}
    where order_status <> 'canceled'
),
mart as (
    select sum(revenue) as total
    from {{ ref('mart_daily_revenue') }}
)
select fact.total as fact_total, mart.total as mart_total
from fact, mart
where abs(fact.total - mart.total) > 0.01
