with expected_and_actual as (

    select
        'dim_players' as model_name,
        (
            select count(distinct player_id)
            from (
                select player_id from {{ ref('stg_players') }}
                union all
                select player_id from {{ ref('stg_appearances') }}
            )
        ) as expected_rows,
        (select count(*) from {{ ref('dim_players') }}) as actual_rows

    union all

    select
        'dim_clubs',
        (
            select count(distinct club_id)
            from (
                select club_id from {{ ref('stg_clubs') }}
                union all
                select home_club_id from {{ ref('stg_games') }}
                union all
                select away_club_id from {{ ref('stg_games') }}
                union all
                select from_club_id from {{ ref('stg_transfers') }}
                union all
                select to_club_id from {{ ref('stg_transfers') }}
                union all
                select current_club_id from {{ ref('stg_player_valuations') }}
                union all
                select current_club_id from {{ ref('stg_players') }}
            )
            where club_id is not null
        ),
        (select count(*) from {{ ref('dim_clubs') }})

    union all

    select
        'dim_competitions',
        (select count(*) from {{ ref('stg_competitions') }}),
        (select count(*) from {{ ref('dim_competitions') }})

    union all

    select
        'fct_club_performance',
        (select count(*) from {{ ref('int_club_performance_summary') }}),
        (select count(*) from {{ ref('fct_club_performance') }})

    union all

    select
        'fct_competition_performance',
        (select count(*) from {{ ref('int_competition_summary') }}),
        (select count(*) from {{ ref('fct_competition_performance') }})

    union all

    select
        'fct_player_performance',
        (select count(*) from {{ ref('int_player_performance_summary') }}),
        (select count(*) from {{ ref('fct_player_performance') }})

    union all

    select
        'fct_player_career_timeline',
        (select count(*) from {{ ref('int_player_season_performance') }}),
        (select count(*) from {{ ref('fct_player_career_timeline') }})

    union all

    select
        'fct_market_value_history',
        (select count(*) from {{ ref('stg_player_valuations') }}),
        (select count(*) from {{ ref('fct_market_value_history') }})

    union all

    select
        'fct_transfers',
        (select count(*) from {{ ref('stg_transfers') }}),
        (select count(*) from {{ ref('fct_transfers') }})
)

select *

from expected_and_actual

where expected_rows != actual_rows
