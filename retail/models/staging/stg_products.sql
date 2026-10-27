with ranked as (

    select
        product_id,
        lower(trim(category)) as category,
        cast(weight_g as integer) as weight_g,
        cast(list_price as decimal(12, 2)) as list_price,
        _loaded_at,
        row_number() over (
            partition by product_id
            order by _loaded_at desc
        ) as rn
    from {{ source('raw', 'products') }}

)

select product_id, category, weight_g, list_price, _loaded_at
from ranked
where rn = 1
