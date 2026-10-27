{% snapshot customers_snapshot %}

{{
    config(
        unique_key='customer_id',
        strategy='check',
        check_cols=['city', 'state']
    )
}}

-- SCD Type 2: every time a customer's city or state changes, dbt closes the old row
-- (dbt_valid_to) and opens a new one. Run after each load: `dbt snapshot`.
select customer_id, city, state
from {{ ref('stg_customers') }}

{% endsnapshot %}
