with season_market_value as (

    select
        player_id,
        extract(year from valuation_date) as season,
        round(avg(market_value_in_eur), 2) as season_market_value

    from {{ ref('stg_player_valuations') }}

    where market_value_in_eur is not null

    group by
        player_id,
        extract(year from valuation_date)

)

select
    a.player_id,
    g.season,
    a.competition_id,

    count(distinct a.game_id) as matches_played,

    sum(a.goals) as total_goals,
    sum(a.assists) as total_assists,
    sum(a.minutes_played) as total_minutes_played,

    sum(a.yellow_cards) as total_yellow_cards,
    sum(a.red_cards) as total_red_cards,

    round(safe_divide(sum(a.goals), count(distinct a.game_id)), 2) as goals_per_match,
    round(safe_divide(sum(a.assists), count(distinct a.game_id)), 2) as assists_per_match,

    round(safe_divide(sum(a.goals), nullif(sum(a.minutes_played), 0)) * 90, 2) as goals_per_90,
    round(safe_divide(sum(a.assists), nullif(sum(a.minutes_played), 0)) * 90, 2) as assists_per_90,

    max(mv.season_market_value) as season_market_value

from {{ ref('stg_appearances') }} a

left join {{ ref('stg_games') }} g
    on a.game_id = g.game_id

left join season_market_value mv
    on a.player_id = mv.player_id
   and g.season = mv.season

group by
    a.player_id,
    g.season,
    a.competition_id