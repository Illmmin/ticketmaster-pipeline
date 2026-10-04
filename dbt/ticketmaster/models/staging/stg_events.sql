with source as (

    select
        payload,
        ingested_at
    from {{ source('raw_data', 'raw_events') }}

),

renamed as (

    select
        json_value(payload, '$.event_id')                          as event_id,
        json_value(payload, '$.name')                               as event_name,
        json_value(payload, '$.url')                                 as event_url,
        safe_cast(json_value(payload, '$.start_date') as date)       as start_date,
        safe_cast(json_value(payload, '$.start_time') as time)       as start_time,
        json_value(payload, '$.status')                              as event_status,
        json_value(payload, '$.segment')                             as segment,
        json_value(payload, '$.genre')                               as genre,
        json_value(payload, '$.sub_genre')                           as sub_genre,
        safe_cast(json_value(payload, '$.price_min') as float64)     as price_min,
        safe_cast(json_value(payload, '$.price_max') as float64)     as price_max,
        json_value(payload, '$.currency')                            as currency,
        json_value(payload, '$.venue_id')                            as venue_id,
        json_value(payload, '$.venue_name')                          as venue_name,
        ingested_at
    from source

),

deduplicated as (

    -- un même événement peut être recollecté sur plusieurs runs (quota, planification) ;
    -- on garde uniquement la version la plus récemment ingérée
    select *
    from renamed
    qualify row_number() over (
        partition by event_id
        order by ingested_at desc
    ) = 1

)

select * from deduplicated
