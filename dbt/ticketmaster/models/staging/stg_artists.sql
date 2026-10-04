with source as (

    select
        json_value(payload, '$.event_id')           as event_id,
        json_value_array(payload, '$.artist_ids')    as artist_ids,
        json_value_array(payload, '$.artist_names')  as artist_names
    from {{ source('raw_data', 'raw_events') }}

),

unnested as (

    -- artist_ids et artist_names sont deux tableaux parallèles (même ordre,
    -- même longueur, construits ensemble dans parsers.py) : on les dézippe
    -- via l'offset commun plutôt que de faire un UNNEST croisé
    select
        event_id,
        artist_id,
        artist_names[safe_offset(id_offset)] as artist_name
    from source,
    unnest(artist_ids) as artist_id with offset as id_offset

)

select *
from unnested
where artist_id is not null
