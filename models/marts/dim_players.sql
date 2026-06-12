with current_players as (

    select
        player_id,
        player_name,
        position,
        sub_position,
        birth_date,
        country_of_birth,
        country_of_citizenship,
        height_in_cm,
        preferred_foot,
        agent_name,
        current_club_id,
        current_club_name,
        last_season

    from {{ ref('stg_players') }}
),

appearance_players as (

    select
        appearances.player_id,

        array_agg(
            appearances.player_name ignore nulls
            order by appearances.appearance_date desc, appearances.appearance_id desc
            limit 1
        )[safe_offset(0)] as player_name,

        array_agg(
            appearances.player_club_id ignore nulls
            order by appearances.appearance_date desc, appearances.appearance_id desc
            limit 1
        )[safe_offset(0)] as latest_club_id,

        max(games.season) as last_season

    from {{ ref('stg_appearances') }} appearances

    inner join {{ ref('stg_games') }} games
        on appearances.game_id = games.game_id

    group by appearances.player_id
)

select *

from current_players

union all

select
    appearance_players.player_id,
    appearance_players.player_name,
    cast(null as string) as position,
    cast(null as string) as sub_position,
    cast(null as date) as birth_date,
    cast(null as string) as country_of_birth,
    cast(null as string) as country_of_citizenship,
    cast(null as int64) as height_in_cm,
    cast(null as string) as preferred_foot,
    cast(null as string) as agent_name,
    appearance_players.latest_club_id as current_club_id,
    clubs.club_name as current_club_name,
    appearance_players.last_season

from appearance_players

left join current_players
    on appearance_players.player_id = current_players.player_id

left join {{ ref('dim_clubs') }} clubs
    on appearance_players.latest_club_id = clubs.club_id

where current_players.player_id is null
