# Data Quality and Validation

## Validation Status

The project was fully validated against BigQuery on June 12, 2026.

| Validation | Result |
| --- | ---: |
| Full project tests | 105 passed |
| Mart-only build | 54 passed |
| Mart models rebuilt | 9 |
| Mart-specific tests | 45 passed |
| Warnings | 0 |
| Errors | 0 |
| Non-null fact-to-dimension orphan keys | 0 |

The mart-only build result contains 9 table models and 45 tests. The full project result contains all source, schema, and singular data tests.

## Current Mart Row Counts

| Model | Rows |
| --- | ---: |
| `dim_players` | 47,702 |
| `dim_clubs` | 9,032 |
| `dim_competitions` | 67 |
| `fct_player_performance` | 28,736 |
| `fct_player_career_timeline` | 189,789 |
| `fct_club_performance` | 3,270 |
| `fct_competition_performance` | 67 |
| `fct_market_value_history` | 507,815 |
| `fct_transfers` | 40,208 |

Row counts represent the BigQuery state at validation time and can change when raw data is refreshed.

## Test Coverage

### Source Tests

Source tests validate required identifiers and uniqueness where the source grain guarantees a unique key.

Examples:

- Player, club, game, competition, event, and lineup identifiers are unique and not null.
- Appearance, transfer, and valuation identifiers required for downstream logic are not null.

### Schema Tests

Schema tests validate:

- Unique and not-null model grains
- Relationships between staged models
- Relationships between mart facts and dimensions

### Singular Business-Rule Tests

The `tests/` directory contains 28 custom SQL tests covering:

- Appearance player-game grain
- Two club-perspective rows per game
- Player, club, competition, transfer, and market-value recalculations
- Intermediate and mart row coverage
- Current dimension record preservation
- Market value and transfer fact source reconciliation
- Player season-performance grain
- Market value selection not occurring after the player's last game
- Player age calculation
- Staging sentinel normalization
- Transfer fee calculations
- Mart values matching intermediate or staging inputs

## Reconciliation Strategy

Critical facts are validated by recalculating expected values from their upstream models and comparing both directions:

```text
expected EXCEPT DISTINCT actual
actual EXCEPT DISTINCT expected
```

Two-decimal floating metrics are normalized to exact `NUMERIC` values before comparison. This prevents BigQuery floating-point execution differences from creating false failures while retaining exact business-level validation.

## Known Raw Source Limitations

These issues originate in the raw dataset and are not introduced by dbt:

| Limitation | Observed count |
| --- | ---: |
| Historical clubs without a recoverable name | 451 |
| Historical players without a recoverable name | 1 |
| Appearance records with minutes above a standard 90-minute match | 3 |
| Appearance players missing from the current players source | 2 |
| Lineup rows whose player is missing from the players source | 326,036 |
| Transfers with unknown transfer fee | 14,387 |
| Transfers with unknown market value | 15,849 |
| Player-season records without a prior eligible valuation | 8,655 |

The raw `clubs.total_market_value` field is also entirely null in the current source snapshot.

### Treatment of Source Limitations

- Missing historical player and club references are retained in dimensions when an identifier exists.
- Missing descriptive fields remain `NULL`; they are not fabricated.
- Missing monetary values remain `NULL` and are excluded naturally from calculations that require them.
- Appearance minutes are preserved because extra time can exceed 90 minutes.
- Seasonal market value remains `NULL` when no valuation exists on or before the relevant last game date.

## Definition of "100% Passing"

For this repository, "100% passing" means:

- Every configured dbt test passes.
- All dbt models build successfully.
- Defined transformation and relationship rules are satisfied.
- No warnings or errors are reported.

It does not mean the external raw dataset has no missing values. Raw source limitations are documented separately so downstream consumers can interpret nulls correctly.

## Recommended Refresh Validation

After every raw data refresh:

```bash
dbt build
dbt test
```

Then compare mart row counts and review any changes in known source limitation counts. New failures should be investigated before BI or ML consumers are refreshed.
