with expected as (

    select
        timeline.player_id,
        players.player_name,
        players.position,
        players.current_club_name,
        timeline.season,
        timeline.competition_id,
        timeline.matches_played,
        timeline.total_goals,
        timeline.total_assists,
        timeline.total_minutes_played,
        timeline.total_yellow_cards,
        timeline.total_red_cards,
        timeline.goals_per_match,
        timeline.assists_per_match,
        timeline.goals_per_90,
        timeline.assists_per_90,
        timeline.season_market_value,
        timeline.season_market_value_date

    from {{ ref('int_player_season_performance') }} timeline

    left join {{ ref('dim_players') }} players
        on timeline.player_id = players.player_id
),

differences as (

    (
        select * replace (
            cast(round(goals_per_match, 2) as numeric) as goals_per_match,
            cast(round(assists_per_match, 2) as numeric) as assists_per_match,
            cast(round(goals_per_90, 2) as numeric) as goals_per_90,
            cast(round(assists_per_90, 2) as numeric) as assists_per_90
        )
        from expected

        except distinct

        select * replace (
            cast(round(goals_per_match, 2) as numeric) as goals_per_match,
            cast(round(assists_per_match, 2) as numeric) as assists_per_match,
            cast(round(goals_per_90, 2) as numeric) as goals_per_90,
            cast(round(assists_per_90, 2) as numeric) as assists_per_90
        )
        from {{ ref('fct_player_career_timeline') }}
    )

    union all

    (
        select * replace (
            cast(round(goals_per_match, 2) as numeric) as goals_per_match,
            cast(round(assists_per_match, 2) as numeric) as assists_per_match,
            cast(round(goals_per_90, 2) as numeric) as goals_per_90,
            cast(round(assists_per_90, 2) as numeric) as assists_per_90
        )
        from {{ ref('fct_player_career_timeline') }}

        except distinct

        select * replace (
            cast(round(goals_per_match, 2) as numeric) as goals_per_match,
            cast(round(assists_per_match, 2) as numeric) as assists_per_match,
            cast(round(goals_per_90, 2) as numeric) as goals_per_90,
            cast(round(assists_per_90, 2) as numeric) as assists_per_90
        )
        from expected
    )
)

select *
from differences
