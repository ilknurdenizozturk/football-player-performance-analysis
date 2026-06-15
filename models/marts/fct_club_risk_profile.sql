select
    to_club_id as club_id,
    to_club_name as club_name,
    count(*) as total_incoming_transfers,
    countif(has_known_transfer_fee) as transfers_with_known_fee,
    avg(fee_to_market_value_ratio) as avg_fee_to_value_ratio,
    avg(fee_market_value_difference_pct) as avg_overpay_pct,
    countif(market_value_direction_after_transfer = 'increase') as transfers_increased_value,
    countif(market_value_direction_after_transfer = 'decrease') as transfers_decreased_value,
    safe_divide(
        countif(market_value_direction_after_transfer = 'increase'),
        countif(has_post_transfer_value_change)
    ) as transfer_success_rate,
    case
        when avg(fee_market_value_difference_pct) > 30
             and safe_divide(
                 countif(market_value_direction_after_transfer = 'increase'),
                 countif(has_post_transfer_value_change)
             ) < 0.4
        then 'High Risk'
        when avg(fee_market_value_difference_pct) > 10 then 'Medium Risk'
        else 'Low Risk'
    end as transfer_risk_category
from {{ ref('fct_transfer_market_value_analysis') }}
where has_post_transfer_value_change = true
  and is_future_transfer = false
group by to_club_id, to_club_name
