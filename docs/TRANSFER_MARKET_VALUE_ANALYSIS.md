# Transfer and Market Value Analysis

## Purpose

`football_mart.fct_transfer_market_value_analysis` is the dedicated analytics mart for evaluating player transfers against market values before and after the transfer.

The table supports:

- Transfer fee premium and discount analysis
- Market value movement after a transfer
- Player transfer history and cumulative fee analysis
- Competition and country context changes around a transfer
- Future transfer filtering
- Auditable matching to the nearest available valuations

## Grain

One row represents one source transfer record.

`transfer_key` is a stable unique key generated from all fields that define the source transfer record. The current table contains 40,208 rows and 40,208 unique transfer keys.

## Market Value Baseline

The fee comparison baseline follows this priority:

1. Use `transfer_record_market_value` when the transfer record provides a market value.
2. Otherwise, use `prior_market_value`, the latest available valuation on or before the transfer date.
3. Leave the baseline null when neither value is available.

`market_value_baseline_source` identifies which rule was applied.

## Main Metric Groups

| Group | Important columns |
| --- | --- |
| Transfer identity | `transfer_key`, `player_id`, `transfer_date`, `transfer_season` |
| Player context | `player_name`, `position`, `sub_position`, `age_at_transfer`, `country_of_citizenship` |
| Transfer lifecycle | `transfer_sequence_number`, `player_transfer_count`, `previous_transfer_date`, `next_transfer_date`, `is_latest_transfer` |
| Fee analysis | `transfer_fee`, `fee_status`, `cumulative_known_transfer_fee`, `total_transfer_fee`, `max_transfer_fee` |
| Fee-to-value analysis | `market_value_baseline`, `fee_market_value_difference`, `fee_market_value_difference_pct`, `fee_to_market_value_ratio` |
| Prior valuation | `prior_valuation_date`, `prior_market_value`, prior club and competition fields |
| Post-transfer valuation | `next_valuation_date`, `next_market_value`, next club and competition fields |
| Post-transfer outcome | `market_value_change_after_transfer`, `market_value_change_after_transfer_pct`, `market_value_direction_after_transfer` |
| Career market value | `first_market_value`, `current_market_value`, `highest_market_value`, `career_market_value_growth_pct` |
| Data availability | `has_known_transfer_fee`, `has_market_value_baseline`, `has_fee_market_value_comparison`, `has_prior_valuation`, `has_next_valuation`, `has_post_transfer_value_change` |

## Current Coverage

| Coverage metric | Rows |
| --- | ---: |
| Total transfer records | 40,208 |
| Transfers with a known fee | 25,821 |
| Transfers with a selected market value baseline | 24,913 |
| Transfers with both a known fee and baseline | 20,001 |
| Transfers with a prior valuation | 24,886 |
| Transfers with a subsequent valuation | 35,077 |
| Transfers with a calculated post-transfer value change | 21,820 |
| Future-dated transfer records | 429 |

## Interpretation Rules

- `fee_status = 'zero_fee'` means the source fee equals zero. It should not automatically be interpreted as a confirmed free transfer.
- `fee_market_value_difference_pct` is null when the fee or baseline is unavailable, or when the baseline is zero.
- `market_value_change_after_transfer_pct` compares the first subsequent valuation with the selected baseline.
- `valuation_context_change` compares competition context from the nearest valuations. It does not independently prove the legal transfer destination or league at the exact transfer time.
- Future-dated transfers are retained and identified with `is_future_transfer`.
- Missing source values remain null and are not estimated.
- Power BI measures should filter with the relevant `has_*` availability field instead of replacing missing monetary values with zero.

## Example Analyses

### Transfer Fee Premium by Season

```sql
select
    transfer_season,
    count(*) as comparable_transfers,
    round(avg(fee_market_value_difference_pct), 2) as avg_fee_premium_pct,
    round(avg(market_value_change_after_transfer_pct), 2) as avg_post_transfer_value_change_pct
from `football_mart.fct_transfer_market_value_analysis`
where has_fee_market_value_comparison
    and not is_future_transfer
group by transfer_season
order by transfer_season desc;
```

### Largest Post-Transfer Market Value Gains

```sql
select
    player_name,
    transfer_date,
    from_club_name,
    to_club_name,
    transfer_fee,
    market_value_baseline,
    next_market_value,
    market_value_change_after_transfer,
    market_value_change_after_transfer_pct,
    days_to_next_valuation
from `football_mart.fct_transfer_market_value_analysis`
where has_post_transfer_value_change
    and days_to_next_valuation <= 365
    and not is_future_transfer
order by market_value_change_after_transfer desc
limit 100;
```

### Competition Context Changes

```sql
select
    valuation_context_change,
    count(*) as transfers,
    round(avg(fee_market_value_difference_pct), 2) as avg_fee_premium_pct,
    round(avg(market_value_change_after_transfer_pct), 2) as avg_value_change_pct
from `football_mart.fct_transfer_market_value_analysis`
where valuation_context_change != 'unavailable'
    and not is_future_transfer
group by valuation_context_change
order by transfers desc;
```

## Physical Design

- Materialization: BigQuery table
- Partitioning: yearly by `transfer_date`
- Clustering: `player_id`, `to_club_id`, `from_club_id`
- Columns: 75, all documented in dbt Docs and BigQuery metadata
- Direct tests: 30

Power BI relationship and measure recommendations are documented in [Power BI Modeling Guide](POWER_BI_MODELING.md).
