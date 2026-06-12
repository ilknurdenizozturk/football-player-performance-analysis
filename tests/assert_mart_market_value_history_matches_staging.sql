with expected as (

    select
        valuations.player_id,
        players.player_name,
        players.position,
        players.sub_position,
        valuations.valuation_date,
        valuations.market_value_in_eur,
        valuations.current_club_id,
        valuations.current_club_name,
        valuations.player_club_domestic_competition_id as competition_id

    from {{ ref('stg_player_valuations') }} valuations

    left join {{ ref('dim_players') }} players
        on valuations.player_id = players.player_id
),

differences as (

    (select * from expected except distinct select * from {{ ref('fct_market_value_history') }})

    union all

    (select * from {{ ref('fct_market_value_history') }} except distinct select * from expected)
)

select *
from differences
