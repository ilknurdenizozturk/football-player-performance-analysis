"""Train and evaluate a leakage-safe player market value regression model."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder


NUMERIC_FEATURES = [
    "season",
    "height_in_cm",
    "age_at_target_date",
    "matches_before_target",
    "competitions_played_before_target",
    "minutes_before_target",
    "goals_before_target",
    "assists_before_target",
    "yellow_cards_before_target",
    "red_cards_before_target",
    "goals_per_90_before_target",
    "assists_per_90_before_target",
    "previous_market_value_eur",
    "days_since_previous_market_value",
    "prior_valuation_count",
    "prior_highest_market_value_eur",
]

CATEGORICAL_FEATURES = [
    "position",
    "sub_position",
    "preferred_foot",
    "country_of_citizenship",
    "competition_id",
    "competition_type",
    "competition_country_name",
    "confederation",
]

TARGET = "target_market_value_eur"
METADATA_COLUMNS = [
    "position",
    "sub_position",
    "competition_country_name",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--dataset", default="football_ml")
    parser.add_argument("--table", default="ml_player_market_value_training")
    parser.add_argument("--score-table", default="ml_player_market_value_scoring")
    parser.add_argument("--credentials")
    parser.add_argument("--test-seasons", type=int, default=2)
    parser.add_argument("--max-rows", type=int)
    parser.add_argument("--output-dir", default="artifacts/player_market_value")
    parser.add_argument(
        "--publish-predictions-table",
        help="Optional BigQuery table name in the selected dataset, written with WRITE_TRUNCATE.",
    )
    parser.add_argument(
        "--publish-current-predictions-table",
        help="Optional BigQuery table name for current active-player predictions.",
    )
    parser.add_argument(
        "--publish-evaluation-metrics-table",
        help="Optional BigQuery table name for overall and segment evaluation metrics.",
    )
    parser.add_argument(
        "--publish-drift-table",
        help="Optional BigQuery table name for current-scoring feature drift metrics.",
    )
    parser.add_argument(
        "--publish-model-registry-table",
        help="Optional BigQuery table name for the latest model-run metadata.",
    )
    return parser.parse_args()


def bigquery_client(args: argparse.Namespace) -> bigquery.Client:
    credentials = None
    if args.credentials:
        credentials = service_account.Credentials.from_service_account_file(
            args.credentials
        )
    return bigquery.Client(project=args.project_id, credentials=credentials)


def load_training_data(args: argparse.Namespace) -> pd.DataFrame:
    client = bigquery_client(args)
    selected_columns = [
        "training_row_key",
        "player_id",
        "player_name",
        "target_market_value_date",
        TARGET,
        *NUMERIC_FEATURES,
        *CATEGORICAL_FEATURES,
    ]
    selected_columns = list(dict.fromkeys(selected_columns))
    limit = f"limit {args.max_rows}" if args.max_rows else ""
    query = f"""
        select {", ".join(selected_columns)}
        from `{args.project_id}.{args.dataset}.{args.table}`
        where {TARGET} > 0
        order by target_market_value_date, training_row_key
        {limit}
    """
    frame = client.query(query).to_dataframe(create_bqstorage_client=False)
    for column in NUMERIC_FEATURES + [TARGET]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype(float)
    for column in CATEGORICAL_FEATURES:
        frame[column] = frame[column].astype(object).where(frame[column].notna(), np.nan)
    return frame


def load_scoring_data(args: argparse.Namespace) -> pd.DataFrame:
    client = bigquery_client(args)
    selected_columns = [
        "scoring_row_key",
        "player_id",
        "player_name",
        "prediction_as_of_date",
        *NUMERIC_FEATURES,
        *CATEGORICAL_FEATURES,
    ]
    selected_columns = list(dict.fromkeys(selected_columns))
    query = f"""
        select {", ".join(selected_columns)}
        from `{args.project_id}.{args.dataset}.{args.score_table}`
        order by scoring_row_key
    """
    frame = client.query(query).to_dataframe(create_bqstorage_client=False)
    for column in NUMERIC_FEATURES:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype(float)
    for column in CATEGORICAL_FEATURES:
        frame[column] = frame[column].astype(object).where(frame[column].notna(), np.nan)
    return frame


def split_by_season(
    frame: pd.DataFrame, test_seasons: int
) -> tuple[pd.DataFrame, pd.DataFrame, list[int]]:
    seasons = sorted(int(season) for season in frame["season"].dropna().unique())
    if len(seasons) <= test_seasons:
        raise ValueError("Not enough distinct seasons for the requested time split.")

    held_out_seasons = seasons[-test_seasons:]
    train = frame[~frame["season"].isin(held_out_seasons)].copy()
    test = frame[frame["season"].isin(held_out_seasons)].copy()
    if train.empty or test.empty:
        raise ValueError("Time split produced an empty train or test dataset.")
    return train, test, held_out_seasons


def build_pipeline() -> Pipeline:
    numeric_pipeline = Pipeline(
        steps=[("imputer", SimpleImputer(strategy="median", add_indicator=True))]
    )
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            (
                "encoder",
                OrdinalEncoder(
                    handle_unknown="use_encoded_value",
                    unknown_value=-1,
                    encoded_missing_value=-1,
                ),
            ),
        ]
    )
    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", numeric_pipeline, NUMERIC_FEATURES),
            ("categorical", categorical_pipeline, CATEGORICAL_FEATURES),
        ],
        verbose_feature_names_out=False,
    )
    model = HistGradientBoostingRegressor(
        learning_rate=0.07,
        max_iter=300,
        max_leaf_nodes=31,
        min_samples_leaf=30,
        l2_regularization=1.0,
        random_state=42,
    )
    return Pipeline(steps=[("preprocessor", preprocessor), ("model", model)])


def regression_metrics(
    actual: np.ndarray, predicted: np.ndarray
) -> dict[str, float | None]:
    absolute_error = np.abs(actual - predicted)
    return {
        "mae_eur": float(mean_absolute_error(actual, predicted)),
        "rmse_eur": float(np.sqrt(mean_squared_error(actual, predicted))),
        "r2": float(r2_score(actual, predicted)) if len(actual) >= 2 else None,
        "wape_pct": float(absolute_error.sum() / actual.sum() * 100),
        "median_absolute_percentage_error_pct": float(
            np.median(absolute_error / actual) * 100
        ),
        "mean_error_eur": float(np.mean(predicted - actual)),
        "within_25_pct": float(np.mean(absolute_error / actual <= 0.25) * 100),
    }


def select_blend_weight(
    actual: np.ndarray, model_prediction: np.ndarray, baseline_prediction: np.ndarray
) -> float:
    candidates = np.linspace(0, 1, 21)
    return float(
        min(
            candidates,
            key=lambda weight: mean_absolute_error(
                actual,
                weight * model_prediction + (1 - weight) * baseline_prediction,
            ),
        )
    )


def prediction_quality_status(frame: pd.DataFrame) -> pd.Series:
    high = (
        frame["previous_market_value_eur"].notna()
        & frame["age_at_target_date"].notna()
        & frame["competition_id"].notna()
        & frame["minutes_before_target"].ge(450)
    )
    medium = (
        frame["previous_market_value_eur"].notna()
        & frame["age_at_target_date"].notna()
        & frame["minutes_before_target"].gt(0)
    )
    return pd.Series(
        np.select([high, medium], ["high", "medium"], default="limited"),
        index=frame.index,
    )


def validate_predictions(
    predictions: pd.DataFrame, key_column: str, prediction_column: str
) -> None:
    if predictions[key_column].duplicated().any():
        raise ValueError(f"Duplicate prediction keys found in {key_column}.")
    values = predictions[prediction_column].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError(f"Invalid values found in {prediction_column}.")
    interval_columns = {
        "prediction_interval_band",
        "prediction_interval_eur",
        "prediction_lower_eur",
        "prediction_upper_eur",
    }
    if interval_columns.issubset(predictions.columns):
        interval_widths = predictions["prediction_interval_eur"].to_numpy(dtype=float)
        lower = predictions["prediction_lower_eur"].to_numpy(dtype=float)
        upper = predictions["prediction_upper_eur"].to_numpy(dtype=float)
        if (
            not np.isfinite(interval_widths).all()
            or (interval_widths <= 0).any()
            or predictions["prediction_interval_band"].isna().any()
            or (lower < 0).any()
            or (lower > values).any()
            or (upper < values).any()
        ):
            raise ValueError("Invalid prediction intervals found.")


def value_band(values: pd.Series) -> pd.Series:
    return pd.cut(
        values,
        bins=[0, 1_000_000, 5_000_000, 20_000_000, np.inf],
        labels=["under_1m", "1m_to_5m", "5m_to_20m", "20m_plus"],
        include_lowest=True,
        right=False,
    ).astype(str)


def calibrate_prediction_intervals(
    actual: np.ndarray, predicted: np.ndarray, quantile: float = 0.9
) -> tuple[float, dict[str, float]]:
    absolute_error = np.abs(actual - predicted)
    default_interval = float(np.quantile(absolute_error, quantile, method="higher"))
    predicted_bands = value_band(pd.Series(predicted)).to_numpy()
    interval_by_band = {
        band: float(
            np.quantile(absolute_error[predicted_bands == band], quantile, method="higher")
        )
        for band in np.unique(predicted_bands)
    }
    return default_interval, interval_by_band


def prediction_interval_widths(
    predicted: np.ndarray,
    default_interval: float,
    interval_by_band: dict[str, float],
) -> tuple[np.ndarray, np.ndarray]:
    bands = value_band(pd.Series(predicted))
    widths = bands.map(interval_by_band).fillna(default_interval).to_numpy(dtype=float)
    return bands.to_numpy(), widths


def evaluation_metrics(predictions: pd.DataFrame, model_version: str) -> pd.DataFrame:
    frame = predictions.copy()
    frame["value_band"] = value_band(frame[TARGET])
    frame["has_previous_market_value"] = frame["previous_market_value_eur"].notna()

    segments = [("overall", None)]
    for column in [
        "season",
        "position",
        "value_band",
        "has_previous_market_value",
        "prediction_quality_status",
    ]:
        segments.extend(
            (column, value) for value in frame[column].dropna().drop_duplicates()
        )

    rows: list[dict[str, object]] = []
    for segment_type, segment_value in segments:
        segment = (
            frame
            if segment_type == "overall"
            else frame[frame[segment_type] == segment_value]
        )
        actual = segment[TARGET].to_numpy(dtype=float)
        predicted = segment["predicted_market_value_eur"].to_numpy(dtype=float)
        baseline = segment["baseline_prediction_eur"].to_numpy(dtype=float)
        model_metrics = regression_metrics(actual, predicted)
        baseline_metrics = regression_metrics(actual, baseline)
        rows.append(
            {
                "model_version": model_version,
                "segment_type": segment_type,
                "segment_value": "all" if segment_value is None else str(segment_value),
                "row_count": len(segment),
                **model_metrics,
                "baseline_mae_eur": baseline_metrics["mae_eur"],
                "mae_improvement_vs_baseline_pct": (
                    (baseline_metrics["mae_eur"] - model_metrics["mae_eur"])
                    / baseline_metrics["mae_eur"]
                    * 100
                    if baseline_metrics["mae_eur"]
                    else 0
                ),
                "interval_coverage_pct": float(
                    (
                        (segment[TARGET] >= segment["prediction_lower_eur"])
                        & (segment[TARGET] <= segment["prediction_upper_eur"])
                    ).mean()
                    * 100
                ),
            }
        )
    return pd.DataFrame(rows)


def population_stability_index(
    reference: pd.Series, current: pd.Series, numeric: bool
) -> float:
    epsilon = 1e-6
    if numeric:
        reference_numeric = pd.to_numeric(reference, errors="coerce")
        current_numeric = pd.to_numeric(current, errors="coerce")
        quantiles = np.unique(
            reference_numeric.dropna().quantile(np.linspace(0, 1, 11)).to_numpy()
        )
        if len(quantiles) < 2:
            return 0.0
        quantiles[0], quantiles[-1] = -np.inf, np.inf
        reference_counts = pd.cut(reference_numeric, quantiles).value_counts(
            sort=False, normalize=True
        )
        current_counts = pd.cut(current_numeric, quantiles).value_counts(
            sort=False, normalize=True
        )
    else:
        reference_counts = (
            reference.fillna("__missing__").astype(str).value_counts(normalize=True)
        )
        current_counts = (
            current.fillna("__missing__").astype(str).value_counts(normalize=True)
        )
        categories = reference_counts.index.union(current_counts.index)
        reference_counts = reference_counts.reindex(categories, fill_value=0)
        current_counts = current_counts.reindex(categories, fill_value=0)

    reference_distribution = np.clip(reference_counts.to_numpy(), epsilon, None)
    current_distribution = np.clip(current_counts.to_numpy(), epsilon, None)
    return float(
        np.sum(
            (current_distribution - reference_distribution)
            * np.log(current_distribution / reference_distribution)
        )
    )


def feature_drift_report(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    model_version: str,
) -> pd.DataFrame:
    rows = []
    reference_season_min = int(reference["season"].min())
    reference_season_max = int(reference["season"].max())
    current_season_min = int(current["season"].min())
    current_season_max = int(current["season"].max())
    for feature, feature_type in [
        *((feature, "numeric") for feature in NUMERIC_FEATURES),
        *((feature, "categorical") for feature in CATEGORICAL_FEATURES),
    ]:
        psi = population_stability_index(
            reference[feature], current[feature], numeric=feature_type == "numeric"
        )
        rows.append(
            {
                "model_version": model_version,
                "feature": feature,
                "feature_type": feature_type,
                "psi": psi,
                "drift_status": (
                    "stable" if psi < 0.1 else "monitor" if psi < 0.25 else "significant"
                ),
                "reference_row_count": len(reference),
                "current_row_count": len(current),
                "reference_season_min": reference_season_min,
                "reference_season_max": reference_season_max,
                "current_season_min": current_season_min,
                "current_season_max": current_season_max,
                "reference_missing_pct": float(reference[feature].isna().mean() * 100),
                "current_missing_pct": float(current[feature].isna().mean() * 100),
            }
        )
    return pd.DataFrame(rows)


def publish_predictions(
    args: argparse.Namespace,
    predictions: pd.DataFrame,
    table_name: str | None,
    write_disposition: str = bigquery.WriteDisposition.WRITE_TRUNCATE,
) -> str | None:
    if not table_name:
        return None

    destination = f"{args.project_id}.{args.dataset}.{table_name}"
    job_config = bigquery.LoadJobConfig(write_disposition=write_disposition)
    if write_disposition == bigquery.WriteDisposition.WRITE_APPEND:
        job_config.schema_update_options = [
            bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION
        ]
    bigquery_client(args).load_table_from_dataframe(
        predictions, destination, job_config=job_config
    ).result()
    return destination


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    frame = load_training_data(args)
    train, test, held_out_seasons = split_by_season(frame, args.test_seasons)
    pre_test_seasons = sorted(int(season) for season in train["season"].unique())
    if len(pre_test_seasons) < 3:
        raise ValueError("At least three pre-test seasons are required.")
    tuning_season = pre_test_seasons[-2]
    calibration_season = pre_test_seasons[-1]
    development = train[train["season"] < tuning_season].copy()
    tuning = train[train["season"] == tuning_season].copy()
    calibration_training = train[train["season"] <= tuning_season].copy()
    calibration = train[train["season"] == calibration_season].copy()
    if development.empty or tuning.empty or calibration.empty:
        raise ValueError("Tuning or calibration split produced an empty dataset.")

    tuning_pipeline = build_pipeline()
    tuning_pipeline.fit(
        development[NUMERIC_FEATURES + CATEGORICAL_FEATURES],
        development[TARGET],
    )
    tuning_model_prediction = np.maximum(
        tuning_pipeline.predict(tuning[NUMERIC_FEATURES + CATEGORICAL_FEATURES]),
        0,
    )
    tuning_baseline_fill = float(development[TARGET].median())
    tuning_baseline_prediction = (
        tuning["previous_market_value_eur"]
        .fillna(tuning_baseline_fill)
        .to_numpy()
    )
    blend_weight = select_blend_weight(
        tuning[TARGET].to_numpy(),
        tuning_model_prediction,
        tuning_baseline_prediction,
    )

    calibration_pipeline = build_pipeline()
    calibration_pipeline.fit(
        calibration_training[NUMERIC_FEATURES + CATEGORICAL_FEATURES],
        calibration_training[TARGET],
    )
    calibration_model_prediction = np.maximum(
        calibration_pipeline.predict(
            calibration[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
        ),
        0,
    )
    calibration_baseline = (
        calibration["previous_market_value_eur"]
        .fillna(float(calibration_training[TARGET].median()))
        .to_numpy()
    )
    calibration_prediction = (
        blend_weight * calibration_model_prediction
        + (1 - blend_weight) * calibration_baseline
    )
    conformal_interval_eur, conformal_interval_by_predicted_value_band = (
        calibrate_prediction_intervals(
            calibration[TARGET].to_numpy(),
            calibration_prediction,
        )
    )

    generated_at = datetime.now(timezone.utc)
    version_input = (
        f"{generated_at.isoformat()}-{len(frame)}-{frame[TARGET].sum()}-"
        f"{tuning_season}-{calibration_season}-{blend_weight}"
    )
    model_version = (
        f"player_market_value_hgbr_v3_"
        f"{generated_at:%Y%m%dT%H%M%SZ}_"
        f"{hashlib.sha256(version_input.encode()).hexdigest()[:8]}"
    )

    pipeline = build_pipeline()
    pipeline.fit(train[NUMERIC_FEATURES + CATEGORICAL_FEATURES], train[TARGET])
    model_prediction = np.maximum(
        pipeline.predict(test[NUMERIC_FEATURES + CATEGORICAL_FEATURES]),
        0,
    )
    baseline_fill = float(train[TARGET].median())
    baseline_prediction = (
        test["previous_market_value_eur"].fillna(baseline_fill).to_numpy()
    )
    predicted = (
        blend_weight * model_prediction
        + (1 - blend_weight) * baseline_prediction
    )
    prediction_interval_band, prediction_interval_eur = prediction_interval_widths(
        predicted,
        conformal_interval_eur,
        conformal_interval_by_predicted_value_band,
    )
    actual = test[TARGET].to_numpy()

    metrics = {
        "training_rows": int(len(train)),
        "test_rows": int(len(test)),
        "train_season_min": int(train["season"].min()),
        "train_season_max": int(train["season"].max()),
        "tuning_season": tuning_season,
        "calibration_season": calibration_season,
        "held_out_test_seasons": held_out_seasons,
        "target_transform": "none",
        "selected_ml_blend_weight": blend_weight,
        "conformal_prediction_interval_eur_90": conformal_interval_eur,
        "conformal_prediction_interval_by_predicted_value_band_eur_90": (
            conformal_interval_by_predicted_value_band
        ),
        "model_version": model_version,
        "ensemble_model": regression_metrics(actual, predicted),
        "ml_only_model": regression_metrics(actual, model_prediction),
        "previous_value_baseline": regression_metrics(actual, baseline_prediction),
    }

    predictions = test[
        [
            "training_row_key",
            "player_id",
            "player_name",
            "season",
            "competition_id",
            "target_market_value_date",
            TARGET,
            "previous_market_value_eur",
            *METADATA_COLUMNS,
        ]
    ].copy()
    predictions["ml_only_prediction_eur"] = model_prediction.round(0)
    predictions["baseline_prediction_eur"] = baseline_prediction.round(0)
    predictions["predicted_market_value_eur"] = predicted.round(0)
    predictions["absolute_error_eur"] = np.abs(actual - predicted).round(0)
    predictions["prediction_interval_band"] = prediction_interval_band
    predictions["prediction_interval_eur"] = prediction_interval_eur.round(0)
    predictions["prediction_lower_eur"] = np.maximum(
        predicted - prediction_interval_eur, 0
    ).round(0)
    predictions["prediction_upper_eur"] = (predicted + prediction_interval_eur).round(0)
    predictions["prediction_quality_status"] = prediction_quality_status(test)
    predictions["selected_ml_blend_weight"] = blend_weight
    predictions["model_version"] = model_version
    predictions["model_generated_at_utc"] = generated_at
    validate_predictions(
        predictions, "training_row_key", "predicted_market_value_eur"
    )
    segment_metrics = evaluation_metrics(predictions, model_version)

    final_pipeline = build_pipeline()
    final_pipeline.fit(
        frame[NUMERIC_FEATURES + CATEGORICAL_FEATURES],
        frame[TARGET],
    )
    model_bundle = {
        "pipeline": final_pipeline,
        "evaluation_pipeline": pipeline,
        "selected_ml_blend_weight": blend_weight,
        "baseline_fill_value_eur": float(frame[TARGET].median()),
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "held_out_test_seasons": held_out_seasons,
        "conformal_prediction_interval_eur_90": conformal_interval_eur,
        "conformal_prediction_interval_by_predicted_value_band_eur_90": (
            conformal_interval_by_predicted_value_band
        ),
        "model_version": model_version,
    }
    joblib.dump(model_bundle, output_dir / "model.joblib")
    predictions.to_csv(output_dir / "test_predictions.csv", index=False)
    segment_metrics.to_csv(output_dir / "evaluation_metrics.csv", index=False)
    published_table = publish_predictions(
        args, predictions, args.publish_predictions_table
    )
    metrics["published_predictions_table"] = published_table
    metrics["published_evaluation_metrics_table"] = publish_predictions(
        args, segment_metrics, args.publish_evaluation_metrics_table
    )

    current_predictions_table = None
    drift_table = None
    if args.publish_current_predictions_table:
        scoring = load_scoring_data(args)
        scoring_ml_prediction = np.maximum(
            final_pipeline.predict(scoring[NUMERIC_FEATURES + CATEGORICAL_FEATURES]),
            0,
        )
        scoring_baseline = (
            scoring["previous_market_value_eur"]
            .fillna(float(frame[TARGET].median()))
            .to_numpy()
        )
        scoring["ml_only_prediction_eur"] = scoring_ml_prediction.round(0)
        scoring["baseline_prediction_eur"] = scoring_baseline.round(0)
        scoring["predicted_market_value_eur"] = (
            blend_weight * scoring_ml_prediction
            + (1 - blend_weight) * scoring_baseline
        ).round(0)
        scoring_interval_band, scoring_interval_eur = prediction_interval_widths(
            scoring["predicted_market_value_eur"].to_numpy(dtype=float),
            conformal_interval_eur,
            conformal_interval_by_predicted_value_band,
        )
        scoring["prediction_interval_band"] = scoring_interval_band
        scoring["prediction_interval_eur"] = scoring_interval_eur.round(0)
        scoring["prediction_lower_eur"] = np.maximum(
            scoring["predicted_market_value_eur"] - scoring_interval_eur, 0
        ).round(0)
        scoring["prediction_upper_eur"] = (
            scoring["predicted_market_value_eur"] + scoring_interval_eur
        ).round(0)
        scoring["prediction_delta_vs_previous_eur"] = (
            scoring["predicted_market_value_eur"]
            - scoring["previous_market_value_eur"]
        ).round(0)
        scoring["prediction_delta_vs_previous_pct"] = (
            scoring["prediction_delta_vs_previous_eur"]
            / scoring["previous_market_value_eur"].replace(0, np.nan)
            * 100
        ).round(2)
        scoring["prediction_quality_status"] = prediction_quality_status(scoring)
        scoring["prediction_is_out_of_time"] = scoring["season"] > frame["season"].max()
        scoring["selected_ml_blend_weight"] = blend_weight
        scoring["model_version"] = model_version
        scoring["model_generated_at_utc"] = generated_at
        validate_predictions(
            scoring, "scoring_row_key", "predicted_market_value_eur"
        )
        scoring.to_csv(output_dir / "current_predictions.csv", index=False)
        current_predictions_table = publish_predictions(
            args, scoring, args.publish_current_predictions_table
        )
        drift_reference = frame[frame["season"] == frame["season"].max()]
        drift = feature_drift_report(
            drift_reference,
            scoring,
            model_version,
        )
        drift.to_csv(output_dir / "feature_drift.csv", index=False)
        drift_table = publish_predictions(args, drift, args.publish_drift_table)
    metrics["published_current_predictions_table"] = current_predictions_table
    metrics["published_drift_table"] = drift_table
    registry = pd.DataFrame(
        [
            {
                "model_version": model_version,
                "model_generated_at_utc": generated_at,
                "training_rows": len(train),
                "test_rows": len(test),
                "train_season_min": int(train["season"].min()),
                "train_season_max": int(train["season"].max()),
                "evaluation_training_rows": len(train),
                "production_training_rows": len(frame),
                "evaluation_train_season_min": int(train["season"].min()),
                "evaluation_train_season_max": int(train["season"].max()),
                "production_train_season_min": int(frame["season"].min()),
                "production_train_season_max": int(frame["season"].max()),
                "tuning_season": tuning_season,
                "calibration_season": calibration_season,
                "test_seasons": ",".join(str(season) for season in held_out_seasons),
                "selected_ml_blend_weight": blend_weight,
                "conformal_prediction_interval_eur_90": conformal_interval_eur,
                "conformal_prediction_interval_by_predicted_value_band_eur_90": (
                    json.dumps(
                        conformal_interval_by_predicted_value_band,
                        sort_keys=True,
                    )
                ),
                **{
                    f"test_{key}": value
                    for key, value in metrics["ensemble_model"].items()
                },
            }
        ]
    )
    metrics["published_model_registry_table"] = publish_predictions(
        args,
        registry,
        args.publish_model_registry_table,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
    )
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
