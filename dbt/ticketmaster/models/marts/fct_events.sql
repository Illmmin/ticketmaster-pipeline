select
    event_id,
    event_name,
    event_url,
    start_date,
    start_time,
    event_status,
    segment,
    genre,
    sub_genre,
    price_min,
    price_max,
    currency,
    venue_id,
    ingested_at
from {{ ref('stg_events') }}
