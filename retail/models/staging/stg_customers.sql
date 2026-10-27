-- One row per customer_id: the latest version loaded.
-- Later batches may re-send a customer with a changed city/state (customer moved).
with ranked as (

    select
        customer_id,
        trim(city) as city,
        upper(trim(state)) as state,
        _loaded_at,
        row_number() over (
            partition by customer_id
            order by _loaded_at desc
        ) as rn
    from {{ source('raw', 'customers') }}

)

select customer_id, city, state, _loaded_at
from ranked
where rn = 1
