select

    club_id,

    matches_played,

    wins,

    draws,

    losses,

    goals_scored,

    goals_conceded,

    goal_difference,

    win_rate,

    avg_goals_scored,

    avg_goals_conceded

from {{ ref('int_club_performance_summary') }}