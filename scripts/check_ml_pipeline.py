"""Smoke-test the player market value preprocessing and model pipeline."""

import numpy as np
import pandas as pd

from train_player_market_value import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    TARGET,
    build_pipeline,
    regression_metrics,
    select_blend_weight,
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
frame.loc[::20, NUMERIC_FEATURES[0]] = np.nan

pipeline = build_pipeline()
pipeline.fit(frame[NUMERIC_FEATURES + CATEGORICAL_FEATURES], frame[TARGET])
prediction = pipeline.predict(frame[NUMERIC_FEATURES + CATEGORICAL_FEATURES])

if not np.isfinite(prediction).all():
    raise SystemExit("ML smoke test produced non-finite predictions.")

baseline = np.full(row_count, frame[TARGET].median())
weight = select_blend_weight(frame[TARGET].to_numpy(), prediction, baseline)
if not 0 <= weight <= 1:
    raise SystemExit("ML smoke test selected an invalid ensemble weight.")

metrics = regression_metrics(frame[TARGET].to_numpy(), prediction)
if not all(np.isfinite(value) for value in metrics.values()):
    raise SystemExit("ML smoke test produced non-finite metrics.")

print("ML pipeline smoke test passed.")
