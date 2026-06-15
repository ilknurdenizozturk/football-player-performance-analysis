"""Smoke-test the player market value preprocessing and model pipeline."""

import numpy as np
import pandas as pd

from train_player_market_value import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    TARGET,
    assert_blocking_quality_gates,
    build_pipeline,
    calibrate_prediction_intervals,
    evaluation_metrics,
    feature_contract_hash,
    feature_drift_report,
    prediction_interval_widths,
    prediction_quality_status,
    quality_gate_report,
    regression_metrics,
    release_status,
    select_blend_weight,
    validate_input_frame,
    validate_predictions,
)


rng = np.random.default_rng(42)
row_count = 500

frame = pd.DataFrame(
    {
        feature: rng.normal(size=row_count)
        for feature in NUMERIC_FEATURES
    }
)
for feature in CATEGORICAL_FEATURES:
    frame[feature] = rng.choice(["a", "b", None], size=row_count)

frame[TARGET] = np.exp(rng.normal(14, 1, size=row_count))
frame["training_row_key"] = np.arange(row_count).astype(str)
frame["player_id"] = np.arange(row_count)
frame["player_name"] = "Synthetic Player"
frame["target_market_value_date"] = pd.Timestamp("2025-01-01")
frame["previous_market_value_eur"] = frame["previous_market_value_eur"].abs()
frame["season"] = rng.choice([2022, 2023, 2024], size=row_count)
frame.loc[::20, "height_in_cm"] = np.nan
validate_input_frame(frame, "training")

if len(feature_contract_hash()) != 64:
    raise SystemExit("ML feature contract hash is invalid.")

pipeline = build_pipeline()
pipeline.fit(frame[NUMERIC_FEATURES + CATEGORICAL_FEATURES], frame[TARGET])
prediction = np.maximum(
    pipeline.predict(frame[NUMERIC_FEATURES + CATEGORICAL_FEATURES]),
    0,
)

if not np.isfinite(prediction).all():
    raise SystemExit("ML smoke test produced non-finite predictions.")

baseline = np.full(row_count, frame[TARGET].median())
weight = select_blend_weight(frame[TARGET].to_numpy(), prediction, baseline)
if not 0 <= weight <= 1:
    raise SystemExit("ML smoke test selected an invalid ensemble weight.")

metrics = regression_metrics(frame[TARGET].to_numpy(), prediction)
if not all(np.isfinite(value) for value in metrics.values()):
    raise SystemExit("ML smoke test produced non-finite metrics.")

frame["predicted_market_value_eur"] = prediction
frame["baseline_prediction_eur"] = frame["previous_market_value_eur"]
default_interval, interval_by_band = calibrate_prediction_intervals(
    frame[TARGET].to_numpy(),
    prediction,
)
frame["prediction_interval_band"], interval_widths = prediction_interval_widths(
    prediction,
    default_interval,
    interval_by_band,
)
frame["prediction_interval_eur"] = interval_widths
frame["prediction_lower_eur"] = np.maximum(prediction - interval_widths, 0)
frame["prediction_upper_eur"] = prediction + interval_widths
frame["prediction_quality_status"] = prediction_quality_status(frame)
validate_predictions(frame, "training_row_key", "predicted_market_value_eur")

segment_metrics = evaluation_metrics(frame, "synthetic")
if segment_metrics.empty:
    raise SystemExit("ML smoke test produced no segment metrics.")

drift = feature_drift_report(frame.iloc[:250], frame.iloc[250:], "synthetic")
if drift.empty or not np.isfinite(drift["psi"]).all():
    raise SystemExit("ML smoke test produced invalid drift metrics.")

quality_gates = quality_gate_report(
    {
        "ensemble_model": metrics,
        "previous_value_baseline": regression_metrics(
            frame[TARGET].to_numpy(),
            frame["baseline_prediction_eur"].to_numpy(),
        ),
    },
    segment_metrics,
    "synthetic",
    pd.Timestamp("2026-01-01", tz="UTC").to_pydatetime(),
    current_predictions=frame,
    drift=drift,
)
if quality_gates.empty or release_status(quality_gates) not in {
    "approved",
    "approved_with_monitoring",
    "rejected",
}:
    raise SystemExit("ML smoke test produced invalid quality gates.")

blocking_failure = quality_gates.copy()
blocking_failure.loc[
    blocking_failure["severity"].eq("blocking"), "passed"
] = False
try:
    assert_blocking_quality_gates(blocking_failure)
except ValueError:
    pass
else:
    raise SystemExit("ML smoke test did not reject failed blocking gates.")

print("ML pipeline smoke test passed.")
