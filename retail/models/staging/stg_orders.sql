-- One row per order_id.
-- Fixes found by profiling the raw data:
--   * exact duplicate rows            -> keep the latest loaded row per order_id
--   * mixed case / padded status      -> lower(trim())
--   * delivered earlier than purchase -> treated as bad data, delivered_at set to NULL
with ranked as (

    select
        order_id,
        customer_id,
        lower(trim(order_status)) as order_status,
        cast(order_purchase_timestamp as timestamp) as purchased_at,
        cast(order_delivered_timestamp as timestamp) as delivered_raw_at,
        _loaded_at,
        row_number() over (
            partition by order_id
            order by _loaded_at desc
        ) as rn
    from {{ source('raw', 'orders') }}

)

select
    order_id,
    customer_id,
    order_status,
    purchased_at,
    case
        when delivered_raw_at >= purchased_at then delivered_raw_at
    end as delivered_at,
    (delivered_raw_at is not null and delivered_raw_at < purchased_at) as has_invalid_delivery_ts,
    _loaded_at
from ranked
where rn = 1
