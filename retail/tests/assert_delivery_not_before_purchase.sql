-- Regression test for a real data bug found in profiling: ~1% of raw orders had
-- delivered timestamps earlier than purchase. stg_orders nulls them out; this test
-- makes sure the mart never lets one through again.
select order_id, purchased_at, delivered_at
from {{ ref('fct_orders') }}
where delivered_at < purchased_at
   or delivery_days < 0
