select
    order_id,
    lower(trim(payment_type)) as payment_type,
    cast(payment_value as decimal(12, 2)) as payment_value,
    _loaded_at
from {{ source('raw', 'payments') }}
