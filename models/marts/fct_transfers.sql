select

    player_id,

    transfer_date,

    transfer_season,

    from_club_id,

    to_club_id,

    from_club_name,

    to_club_name,

    transfer_fee,

    market_value_in_eur,

    player_name,

    transfer_fee - market_value_in_eur as fee_market_value_difference,

    round(
        safe_divide(transfer_fee - market_value_in_eur, nullif(market_value_in_eur, 0)) * 100,
        2
    ) as fee_market_value_difference_pct

from {{ ref('stg_transfers') }}