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