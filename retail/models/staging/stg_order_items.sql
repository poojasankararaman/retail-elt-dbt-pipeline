-- Grain: one row per (order_id, order_item_id).
-- Orphan items (order_id not in orders) are kept here and flagged by a warn-level
-- relationships test; marts only use items that join to a real order.
select
    order_id,
    cast(order_item_id as integer) as order_item_id,
    product_id,
    cast(price as decimal(12, 2)) as price,
    cast(freight_value as decimal(12, 2)) as freight_value,
    _loaded_at
from {{ source('raw', 'order_items') }}
qualify row_number() over (
    partition by order_id, order_item_id
    order by _loaded_at desc
) = 1
