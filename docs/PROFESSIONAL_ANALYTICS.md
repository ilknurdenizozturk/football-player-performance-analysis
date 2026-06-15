# Professional Analytics Layer

## Purpose

This layer turns the transformed football dataset into governed decision products. It adds comparable transfer outcomes, cohort and coverage controls, match-level performance, club and agent portfolio analysis, a Semantic Layer contract, historical snapshots, and version-controlled Power BI assets.

## Production Assets

| Asset | Grain | Decision use |
| --- | --- | --- |
| `fct_transfer_fixed_horizon_outcomes` | Historical transfer | Compare value outcomes at 90, 180, and 365 days |
| `fct_transfer_cohort_performance` | Cohort and horizon | Compare robust cohort outcomes with sample-size controls |
| `fct_data_coverage_bias` | Coverage segment | Identify missingness and selection-bias risk before reporting |
| `fct_club_transfer_portfolio` | Club and transfer season | Analyze spend, income, fee premium, and observed outcomes |
| `fct_transfer_success_labels` | Observed 365-day transfer | Provide a fixed-horizon 20% growth label for classification and risk analysis |
| `fct_club_risk_profile` | Destination club | Govern club risk with success, coverage, and minimum-sample controls |
| `fct_match` | Match | Analyze match result and tactical context |
| `fct_player_match_performance` | Appearance | Analyze player performance and club result |
| `fct_player_rolling_form` | Appearance | Track trailing-five-appearance form |
| `fct_club_season_performance` | Club, season, competition | Compare seasonal club performance |
| `fct_agent_portfolio` | Agent | Analyze represented-player value and performance portfolio |
| `fct_analytics_refresh_audit` | dbt invocation | Audit source volumes, mart volumes, and coverage changes |

Current production row counts are 39,780 fixed-horizon transfers, 8,584 observed fixed-horizon success labels, 5,714 club risk profiles, 156 cohort rows, 53 coverage segments, 30,311 club-season transfer portfolios, 88,807 matches, 1,885,688 player-match rows, 1,885,688 rolling-form rows, 21,583 club-season rows, and 3,849 agent portfolios.

## Transfer Outcome Governance

The fixed-horizon mart selects the nearest valuation within plus or minus 30 days of each 90, 180, and 365-day target. It separates outcomes into:

- `observed`: a comparable follow-up valuation exists.
- `missing_baseline`: a follow-up may exist, but the transfer-time comparison baseline is unavailable.
- `not_yet_observable`: the source snapshot has not reached the complete outcome window.
- `missing_followup`: the outcome window is complete but no comparable valuation exists.

The current historical-transfer population contains 39,780 rows. Overall coverage is:

| Measure | Coverage |
| --- | ---: |
| Known transfer fee | 63.85% |
| Market-value baseline | 61.61% |
| Fee-to-value comparison | 49.27% |
| 90-day outcome | 15.86% |
| 180-day outcome | 24.39% |
| 365-day outcome | 21.58% |
| Pre-transfer 180-day performance | 22.40% |
| Post-transfer 180-day performance | 23.73% |

The overall segment is classified `high_bias_risk`. Decision-facing reporting must show coverage beside outcome metrics and must not generalize observed outcomes to all transfers without qualification.

## Statistical Rules

- Cohort rows expose mean, median, interquartile range, standard deviation, approximate 95% confidence interval, sample size, and coverage.
- Transfer success is defined only on observed 365-day outcomes and requires at least 20% market-value growth.
- Club risk is classified as `insufficient_data` until at least 30 comparable 365-day outcomes exist.
- A cohort requires at least 30 observed outcomes before it is eligible for directional reporting.
- Skewed transfer outcomes should prioritize median and interquartile range.
- Observational comparisons are associations, not causal estimates.
- Classical A/B testing is not supported because randomized assignment and exposure data do not exist.

The version-controlled SQL analyses in `analyses/` provide cohort reporting, matched observational comparison, manager and formation benchmarking, agent portfolio benchmarking, and a data-coverage release gate.

## Semantic And BI Governance

`models/semantic.yml` defines two semantic models and seven governed metrics. `time_spine_daily` provides the required daily Semantic Layer calendar. `models/exposures.yml` records the Power BI and ML consumers that depend on production models.

Power BI assets are version controlled:

- `powerbi/MODEL_SPEC.md` defines supported pages and decision rules.
- `powerbi/MEASURES.dax` defines governed measures.
- `docs/KPI_DICTIONARY.md` defines KPI population, null, and interpretation rules.

## Historical And Refresh Governance

`snap_player_profiles` and `snap_club_profiles` preserve Type-2 history for changing profile attributes. Each key must have exactly one current row and valid historical intervals.

`fct_analytics_refresh_audit` appends one row per dbt invocation. It tracks source and mart row counts, key transfer-coverage metrics, high-bias segments, and insufficient cohort samples. `assert_refresh_audit_volume_stability` blocks a refresh when critical row volumes change by more than 50% from the prior audit.

## Release Gate

A professional analytics release requires:

1. `dbt source freshness --selector raw_sources` passes.
2. Snapshots complete successfully.
3. All models build and all tests pass.
4. Documentation coverage remains 100%.
5. Coverage-bias and refresh-audit outputs are reviewed.
6. ML blocking gates pass and monitoring warnings are disclosed.
