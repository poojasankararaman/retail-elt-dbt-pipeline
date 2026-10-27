select
    product_id,
    category,
    weight_g,
    list_price
from {{ ref('stg_products') }}
