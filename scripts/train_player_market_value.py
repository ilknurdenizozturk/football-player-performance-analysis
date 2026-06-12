"""Train and evaluate a leakage-safe player market value regression model."""

from __future__ import annotations

import argparse
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


def regression_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    absolute_error = np.abs(actual - predicted)
    return {
        "mae_eur": float(mean_absolute_error(actual, predicted)),
        "rmse_eur": float(np.sqrt(mean_squared_error(actual, predicted))),
        "r2": float(r2_score(actual, predicted)),
        "wape_pct": float(absolute_error.sum() / actual.sum() * 100),
        "median_absolute_percentage_error_pct": float(
            np.median(absolute_error / actual) * 100
        ),
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


def publish_predictions(
    args: argparse.Namespace, predictions: pd.DataFrame, table_name: str | None
) -> str | None:
    if not table_name:
        return None

    destination = f"{args.project_id}.{args.dataset}.{table_name}"
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
    )
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
    validation_season = int(train["season"].max())
    development = train[train["season"] < validation_season].copy()
    validation = train[train["season"] == validation_season].copy()
    if development.empty or validation.empty:
        raise ValueError("Validation split produced an empty dataset.")

    validation_pipeline = build_pipeline()
    validation_pipeline.fit(
        development[NUMERIC_FEATURES + CATEGORICAL_FEATURES],
        development[TARGET],
    )
    validation_model_prediction = np.maximum(
        validation_pipeline.predict(
            validation[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
        ),
        0,
    )
    validation_baseline_fill = float(development[TARGET].median())
    validation_baseline_prediction = (
        validation["previous_market_value_eur"]
        .fillna(validation_baseline_fill)
        .to_numpy()
    )
    blend_weight = select_blend_weight(
        validation[TARGET].to_numpy(),
        validation_model_prediction,
        validation_baseline_prediction,
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
    actual = test[TARGET].to_numpy()

    metrics = {
        "training_rows": int(len(train)),
        "test_rows": int(len(test)),
        "train_season_min": int(train["season"].min()),
        "train_season_max": int(train["season"].max()),
        "validation_season": validation_season,
        "held_out_test_seasons": held_out_seasons,
        "target_transform": "none",
        "selected_ml_blend_weight": blend_weight,
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
        ]
    ].copy()
    predictions["ml_only_prediction_eur"] = model_prediction.round(0)
    predictions["baseline_prediction_eur"] = baseline_prediction.round(0)
    predictions["predicted_market_value_eur"] = predicted.round(0)
    predictions["absolute_error_eur"] = np.abs(actual - predicted).round(0)
    predictions["selected_ml_blend_weight"] = blend_weight
    predictions["model_generated_at_utc"] = datetime.now(timezone.utc)

    model_bundle = {
        "pipeline": pipeline,
        "selected_ml_blend_weight": blend_weight,
        "baseline_fill_value_eur": baseline_fill,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "held_out_test_seasons": held_out_seasons,
    }
    joblib.dump(model_bundle, output_dir / "model.joblib")
    predictions.to_csv(output_dir / "test_predictions.csv", index=False)
    published_table = publish_predictions(
        args, predictions, args.publish_predictions_table
    )
    metrics["published_predictions_table"] = published_table

    current_predictions_table = None
    if args.publish_current_predictions_table:
        scoring = load_scoring_data(args)
        final_pipeline = build_pipeline()
        final_pipeline.fit(
            frame[NUMERIC_FEATURES + CATEGORICAL_FEATURES],
            frame[TARGET],
        )
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
        scoring["selected_ml_blend_weight"] = blend_weight
        scoring["model_generated_at_utc"] = datetime.now(timezone.utc)
        scoring.to_csv(output_dir / "current_predictions.csv", index=False)
        current_predictions_table = publish_predictions(
            args, scoring, args.publish_current_predictions_table
        )
    metrics["published_current_predictions_table"] = current_predictions_table
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
