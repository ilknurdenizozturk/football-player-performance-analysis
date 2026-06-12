# Operations Runbook

## Purpose

This runbook describes how to configure, validate, build, and publish the dbt project safely.

## Prerequisites

- Python 3.10+
- `dbt-bigquery` 1.11+
- Google Cloud service account with BigQuery job and dataset permissions
- Raw tables loaded into `football_raw`
- BigQuery processing location matching the source datasets

## Security Rules

- Never commit a service account JSON file.
- Keep `profiles.yml` outside the repository or in an ignored local directory.
- Do not place credentials in SQL, YAML model files, README files, logs, or GitHub issues.
- Use separate development and production targets when multiple environments are available.

## Profile Example

```yaml
default:
  target: dev
  outputs:
    dev:
      type: bigquery
      method: service-account
      project: YOUR_GCP_PROJECT_ID
      dataset: football
      keyfile: /absolute/path/to/service-account.json
      threads: 4
      location: EU
```

The source project is configured in `models/staging/sources.yml`. Update its `database` value when running in another Google Cloud project.

## First-Time Validation

```bash
dbt --version
dbt debug
dbt parse
```

Expected outcome:

- BigQuery connection succeeds.
- The project parses without errors.
- All sources and models are discovered.

## Build Commands

### Full Build

Build all models and run their tests:

```bash
dbt build
```

### Layer Builds

```bash
dbt build --select path:models/staging
dbt build --select path:models/intermediate
dbt build --select path:models/marts
```

### Tests Only

```bash
dbt test
dbt test --select path:models/marts
```

### Generate dbt Documentation

```bash
dbt docs generate
dbt docs serve
```

Generated files under `target/` are local artifacts and should not be committed.

## Deployment Procedure

This repository currently has no automated GitHub Actions deployment workflow. Deployment has two explicit parts:

1. Build the dbt models in BigQuery.
2. Publish the validated code to GitHub.

Recommended sequence:

```bash
dbt build
git diff --check
git status
git add --all
git commit -m "describe the change"
git push origin main
```

Do not push a model change when `dbt build` or required tests fail.

## Validation Checklist

- `dbt debug` succeeds.
- `dbt build` completes with no errors.
- `dbt test` completes with no warnings or errors.
- Mart row coverage tests pass.
- Fact-to-dimension relationship tests pass.
- Source reconciliation tests pass.
- `git diff --check` reports no formatting errors.
- No credentials or generated `target/` artifacts are staged.

## Troubleshooting

### BigQuery Location Error

Ensure the profile `location` matches the raw and target datasets. The validated environment uses `EU`.

### Source Not Found

Check:

- The `database` value in `models/staging/sources.yml`
- The raw dataset name `football_raw`
- Service account dataset permissions

### Unexpected Relationship Failures

Run the relevant staging and dimension models before the facts:

```bash
dbt build --select path:models/staging
dbt build --select path:models/intermediate
dbt build --select path:models/marts
```

Historical players and clubs should be retained by `dim_players` and `dim_clubs`; a new orphan normally indicates a newly introduced source path that must be included in the appropriate dimension.

### Floating-Point Reconciliation Failure

Business metrics are rounded to two decimal places. Tests normalize these fields to BigQuery `NUMERIC` before exact comparison. New floating metrics should follow the same pattern.

### Raw Data Quality Changes

Consult [Data Quality](DATA_QUALITY.md). Missing raw values are acceptable only when documented and intentionally preserved. A new test failure should not be suppressed without understanding the upstream change.
