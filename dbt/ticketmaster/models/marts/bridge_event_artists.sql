-- Un événement peut avoir plusieurs artistes (tête d'affiche + invités) et un
-- artiste peut apparaître sur plusieurs événements : table de liaison dédiée
-- plutôt que de dénormaliser dans fct_events.
select distinct
    event_id,
    artist_id
from {{ ref('stg_artists') }}
