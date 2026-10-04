select
    venue_id,
    venue_name
from {{ ref('stg_venues') }}
