select distinct
    artist_id,
    artist_name
from {{ ref('stg_artists') }}
where artist_id is not null
