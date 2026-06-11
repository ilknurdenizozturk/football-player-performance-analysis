select
    g.competition_id,

    c.competition_name,
    c.competition_type,
    c.country_name,
    c.confederation,

    count(distinct g.game_id) as matches_played,

    sum(g.home_club_goals + g.away_club_goals) as total_goals,

    round(
        avg(g.home_club_goals + g.away_club_goals),
        2
    ) as avg_goals_per_match,

    count(distinct g.home_club_id) + count(distinct g.away_club_id) as club_participation_count,

    round(avg(g.attendance), 2) as avg_attendance

from {{ ref('stg_games') }} g

left join {{ ref('stg_competitions') }} c
    on g.competition_id = c.competition_id

group by
    g.competition_id,
    c.competition_name,
    c.competition_type,
    c.country_name,
    c.confederation