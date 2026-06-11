select

    player_id,

    valuation_date,

    market_value_in_eur,

    current_club_id,

    current_club_name,

    player_club_domestic_competition_id as competition_id

from {{ ref('stg_player_valuations') }}