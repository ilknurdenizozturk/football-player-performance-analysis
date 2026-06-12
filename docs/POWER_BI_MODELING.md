# Power BI Modeling Guide

## Recommended Dataset

Connect Power BI to the BigQuery `football_mart` dataset. The mart layer is materialized as tables and is the supported BI interface. Do not build report relationships directly against staging or intermediate views.

## Recommended Star Schema

| Dimension | Recommended fact relationships |
| --- | --- |
| `dim_players` | Player facts on `player_id` |
| `dim_clubs` | Club facts and transfer club roles on `club_id` |
| `dim_competitions` | Competition facts on `competition_id` |
| `dim_date` | Fact business dates on `date_day` |

Use single-direction, one-to-many relationships from dimensions to facts. For transfer analysis, `transfer_date` should normally be the active date relationship. Prior valuation, next valuation, and other date roles should be inactive relationships used with `USERELATIONSHIP`, or separate role-playing date dimensions.

## NULL Semantics

Canonical nullable fields preserve source truth:

- `NULL` monetary values mean unavailable or unknown, not zero.
- `0` transfer fee is a recorded zero value and remains distinguishable through `fee_status = 'zero_fee'`.
- Historical dimension rows can contain limited attributes because only their identifiers were available from historical facts.
- Calculated comparison values remain `NULL` when their required inputs are unavailable.

Do not use Power Query or DAX to replace unknown transfer fees, market values, or value changes with zero. Doing so changes totals, averages, and comparison populations.

## Fields for Visuals

Use these non-null fields for visual categories and slicers:

| Canonical field | Visual field |
| --- | --- |
| `dim_players.player_name` | `dim_players.player_name_display` |
| `dim_players.position` | `dim_players.position_display` |
| `dim_players.current_club_name` | `dim_players.current_club_name_display` |
| `dim_clubs.club_name` | `dim_clubs.club_name_display` |

Use canonical fields when analyzing missing-data rates. Use `player_record_type`, `club_record_type`, and profile-completeness fields to separate current source profiles from limited historical references.

For current club profile reports, filter `club_record_type = "current_profile"`. The current dimension contains 796 current profiles and 8,236 historical-reference rows retained for referential integrity.

## Availability Flags

Use fact-table availability flags before calculating KPIs from optional values:

| Analysis | Required filter |
| --- | --- |
| Transfer fee averages | `has_known_transfer_fee = TRUE` |
| Fee-to-market-value comparison | `has_fee_market_value_comparison = TRUE` |
| Transfer market-value baseline | `has_market_value_baseline = TRUE` |
| Post-transfer value movement | `has_post_transfer_value_change = TRUE` |
| Current player market value | `has_current_market_value = TRUE` |
| Seasonal market value | `has_season_market_value = TRUE` |
| Valuation club or competition breakdown | `has_club_context = TRUE` or `has_competition_context = TRUE` |

Example DAX:

```dax
Average Fee Premium % =
CALCULATE(
    AVERAGE(fct_transfer_market_value_analysis[fee_market_value_difference_pct]),
    fct_transfer_market_value_analysis[has_fee_market_value_comparison] = TRUE(),
    fct_transfer_market_value_analysis[is_future_transfer] = FALSE()
)
```

## Date Modeling

Mark `dim_date[date_day]` as the Power BI date table. Sort:

- `calendar_month_name` by `calendar_month_number`
- `calendar_month_short_name` by `calendar_month_number`
- `calendar_year_month` by `calendar_year_month_sort`

The dimension is continuous from July 1, 1993 through June 30, 2030 in the current source snapshot. It contains 13,514 rows and is protected by uniqueness, not-null, and continuity tests.

## Report View Recommendations

- Hide technical keys from report consumers after relationships are created.
- Hide `dim_clubs.total_market_value`; it is entirely null in the current raw source snapshot.
- Keep `has_*`, `record_type`, completeness, status, and future-date fields visible for filters and quality checks.
- Default historical transfer reports to `is_future_transfer = FALSE`.
- Keep NULL values in imported data and handle visual labels with the provided display fields.

## Refresh Gate

Refresh Power BI only after these commands pass:

```bash
dbt source freshness --selector raw_sources
dbt build
python scripts/check_documentation_coverage.py
```

The latest June 12, 2026 validation passed all 12 freshness checks, all 190 full-build items, all 111 mart-build items, and documentation for all 486 model columns.
