select
    transfer_key,
    player_id,
    player_name,
    position,
    age_at_transfer,
    transfer_date,
    transfer_year,
    transfer_season,
    from_club_id,
    from_club_name,
    to_club_id,
    to_club_name,
    transfer_fee,
    fee_status,
    has_known_transfer_fee,
    transfer_record_market_value,
    fee_to_market_value_ratio,
    fee_market_value_difference_pct,
    market_value_change_after_transfer_pct,
    market_value_direction_after_transfer,
    case
        when market_value_change_after_transfer_pct >= 20 then 1
        when market_value_change_after_transfer_pct is not null then 0
        else null
    end as is_successful_transfer
from {{ ref('fct_transfer_market_value_analysis') }}
where has_post_transfer_value_change = true
  and is_future_transfer = false
  