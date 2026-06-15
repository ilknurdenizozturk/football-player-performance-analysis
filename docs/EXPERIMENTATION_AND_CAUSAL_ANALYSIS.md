# Experimentation and Causal Analysis

## Current Limitation

The source dataset does not contain randomized treatment assignment, experiment identifiers, exposure timestamps, or a pre-registered success metric. Therefore, classical A/B testing cannot be performed honestly with the current data.

## Supported Observational Analysis

`analyses/transfer_observational_matched_comparison.sql` compares country-change and same-competition transfers only inside matched transfer-year, position, age-band, and fee-premium strata. This reduces visible composition differences but does not prove causality.

Every observational comparison must:

- Label results as associative, not causal.
- Require adequate observed outcomes in both comparison groups.
- Report fixed-horizon outcome coverage.
- Run sensitivity checks across alternative strata and horizons.
- Avoid conclusions when coverage-bias risk is high.

## Required Schema for a Future A/B Test

| Field | Purpose |
| --- | --- |
| `experiment_id` | Stable experiment identifier |
| `subject_id` | Randomized unit |
| `variant` | Control or treatment assignment |
| `assigned_at` | Assignment timestamp |
| `exposed_at` | Actual exposure timestamp |
| `primary_metric_name` | Pre-registered primary metric |
| `outcome_value` | Measured outcome |
| `outcome_window_days` | Pre-registered measurement window |
| `assignment_probability` | Randomization probability |

No analysis should be called an A/B test until these fields and randomization checks exist.
