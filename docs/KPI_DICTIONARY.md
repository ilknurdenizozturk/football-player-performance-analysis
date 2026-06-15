# KPI Dictionary

## Governance Rules

- Every KPI must identify its grain, eligible population, null treatment, and supported decision.
- Unknown monetary values remain `NULL`; they are never treated as zero.
- Transfer outcome KPIs use comparable fixed windows and expose observation coverage.
- Cohort conclusions require `meets_minimum_sample_size = TRUE`; directional results require at least 30 observed outcomes.
- Coverage and bias-risk fields must be shown beside decision-facing transfer metrics.

## Transfer KPIs

| KPI | Definition | Supported model |
| --- | --- | --- |
| Fee premium percent | `(transfer_fee - market_value_baseline) / market_value_baseline * 100` | `fct_transfer_market_value_analysis` |
| 90/180/365-day value change percent | Nearest valuation within plus or minus 30 days of the target horizon versus transfer baseline | `fct_transfer_fixed_horizon_outcomes` |
| Outcome coverage percent | Observed comparable outcomes divided by cohort transfers | `fct_transfer_cohort_performance` |
| Positive outcome rate percent | Observed outcomes above the transfer baseline divided by observed outcomes | `fct_transfer_cohort_performance` |
| Net transfer spend | Known inbound fees minus known outbound fees | `fct_club_transfer_portfolio` |
| Fixed-horizon transfer success rate | Observed 365-day outcomes with at least 20% market-value growth divided by observed 365-day outcomes | `fct_club_risk_profile` |
| Coverage-bias risk | Rule-based risk using sample size and material missingness | `fct_data_coverage_bias` |

## Performance KPIs

| KPI | Definition | Supported model |
| --- | --- | --- |
| Club points | Three points for a win, one for a draw, zero for a loss | `fct_club_season_performance` |
| Rolling five goals per 90 | Goals in the trailing five player appearances divided by minutes, multiplied by 90 | `fct_player_rolling_form` |
| Win rate percent | Wins divided by matches played, multiplied by 100 | `fct_club_season_performance` |
| Player match points | Points earned by the represented club in the player's appearance | `fct_player_match_performance` |

## Statistical Interpretation

- Prefer median and interquartile range for skewed transfer outcomes.
- Mean confidence intervals are approximate and should not be interpreted as causal effects.
- Segment comparisons must be accompanied by observed sample size and coverage.
- Randomized A/B terminology is prohibited unless treatment assignment was randomized and logged.
