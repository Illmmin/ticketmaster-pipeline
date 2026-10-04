with source as (

    select payload
    from {{ source('raw_data', 'raw_events') }}

),

venues as (

    select distinct
        json_value(payload, '$.venue_id')   as venue_id,
        json_value(payload, '$.venue_name') as venue_name
    from source
    where json_value(payload, '$.venue_id') is not null

)

select * from venues
