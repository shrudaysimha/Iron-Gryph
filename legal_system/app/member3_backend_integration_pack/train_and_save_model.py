"""Train Member 3's weather-aware arrival model and save it for an API.

Input: hourly_arrivals_with_weather.csv in the same folder.
Output: surge_model.joblib in the same folder.

Prototype only: historical US arrival counts and Des Moines, Iowa weather proxy.
Not validated for real hospital operations or clinical/staffing decisions.
"""
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

BASE_DIR = Path(__file__).resolve().parent
CANDIDATE_DATA_FILES = [
    BASE_DIR / "hourly_arrivals_with_weather.csv",
    BASE_DIR.parent.parent / "surge predict" / "hourly_arrivals_with_weather.csv",
    Path.cwd() / "legal_system" / "surge predict" / "hourly_arrivals_with_weather.csv",
    Path.cwd() / "surge predict" / "hourly_arrivals_with_weather.csv",
    Path.cwd() / "hourly_arrivals_with_weather.csv",
]


def resolve_data_file() -> Path:
    for candidate in CANDIDATE_DATA_FILES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Cannot find hourly_arrivals_with_weather.csv in any expected location: "
        f"{[str(p) for p in CANDIDATE_DATA_FILES]}. Run download_align_weather.py first."
    )


MODEL_FILE = BASE_DIR / "surge_model.joblib"
APP_MODEL_DIR = BASE_DIR.parent.parent.parent / "app" / "ml" / "saved_models"
RANDOM_STATE = 42
WEATHER_NUMERIC = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
]
WEATHER_REQUIRED = WEATHER_NUMERIC + ["weather_code"]


def build_features(data: pd.DataFrame):
    """Build the same time/arrival/weather features used by the training model."""
    arrivals = data["arrivals"].astype(float)
    features = pd.DataFrame(index=data.index)
    features["hour"] = data.index.hour
    features["day_of_week"] = data.index.dayofweek
    features["month"] = data.index.month
    features["arrivals_now"] = arrivals
    features["arrivals_1h_ago"] = arrivals.shift(1)
    features["arrivals_2h_ago"] = arrivals.shift(2)
    features["arrivals_24h_ago"] = arrivals.shift(24)
    features["arrivals_168h_ago"] = arrivals.shift(168)

    for col in WEATHER_NUMERIC:
        features[col] = data[col]

    code_text = data["weather_code"].round().astype("Int64").astype("string")
    weather_dummies = pd.get_dummies(code_text, prefix="weather_code", dtype=int)
    weather_dummies.index = data.index
    features = pd.concat([features, weather_dummies], axis=1)
    features.loc[~data[WEATHER_REQUIRED].notna().all(axis=1), :] = np.nan
    return features, code_text


def main() -> None:
    data_file = resolve_data_file()
    print(f"Loading data from: {data_file}")
    data = pd.read_csv(data_file, parse_dates=["timestamp"])
    required = {"timestamp", "arrivals", *WEATHER_REQUIRED}
    missing = required - set(data.columns)
    if missing:
        raise ValueError(f"CSV is missing required columns: {sorted(missing)}")

    for col in ["arrivals", *WEATHER_REQUIRED]:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data = data.drop_duplicates("timestamp").set_index("timestamp").sort_index()
    if data.empty:
        raise ValueError("The CSV contains no usable rows.")

    full_index = pd.date_range(data.index.min(), data.index.max(), freq="h")
    data = data.reindex(full_index)
    features, code_text = build_features(data)
    target = data["arrivals"].shift(-1) + data["arrivals"].shift(-2)
    target.name = "arrivals_next_2h"
    model_data = pd.concat([features, target], axis=1).dropna()
    feature_cols = list(features.columns)

    if len(model_data) < 100:
        raise ValueError(
            f"Only {len(model_data)} complete examples. Check data completeness."
        )

    # A chronological holdout prevents randomly mixing earlier and later records.
    split_position = int(len(data) * 0.80)
    split_time = data.index[split_position]
    train_cutoff = split_time - pd.Timedelta(hours=2)
    train = model_data[model_data.index < train_cutoff]
    test = model_data[model_data.index >= split_time]
    if train.empty or test.empty:
        raise ValueError("Not enough complete observations for a chronological split.")

    evaluation_model = RandomForestRegressor(
        n_estimators=250, min_samples_leaf=3, random_state=RANDOM_STATE, n_jobs=-1
    )
    evaluation_model.fit(train[feature_cols], train["arrivals_next_2h"])
    predictions = np.clip(evaluation_model.predict(test[feature_cols]), 0, None)
    model_mae = float(mean_absolute_error(test["arrivals_next_2h"], predictions))
    baseline_predictions = np.clip(test["arrivals_now"] + test["arrivals_1h_ago"], 0, None)
    baseline_mae = float(mean_absolute_error(test["arrivals_next_2h"], baseline_predictions))

    # These are dataset-relative demonstration thresholds, not hospital thresholds.
    low_cutoff = float(train["arrivals_next_2h"].quantile(0.50))
    high_cutoff = float(train["arrivals_next_2h"].quantile(0.80))

    final_model = RandomForestRegressor(
        n_estimators=250, min_samples_leaf=3, random_state=RANDOM_STATE, n_jobs=-1
    )
    final_model.fit(model_data[feature_cols], model_data["arrivals_next_2h"])

    known_weather_codes = sorted(
        str(int(float(value))) for value in code_text.dropna().unique()
    )
    bundle = {
        "model": final_model,
        "feature_cols": feature_cols,
        "low_cutoff": low_cutoff,
        "high_cutoff": high_cutoff,
        "model_test_mae": model_mae,
        "baseline_test_mae": baseline_mae,
        "test_period_starts": str(split_time),
        "known_weather_codes": known_weather_codes,
        "horizon_hours": 2,
        "data_note": (
            "Historical US research arrival data; Des Moines, Iowa weather is an "
            "approximate proxy; not validated for a local hospital."
        ),
    }
    joblib.dump(bundle, MODEL_FILE)
    if APP_MODEL_DIR.exists():
        joblib.dump(bundle, APP_MODEL_DIR / "surge_model.joblib")
        print(f"Synced model to backend: {APP_MODEL_DIR / 'surge_model.joblib'}")

    print("\n=== MEMBER 3: TRAIN AND SAVE MODEL ===")
    print(f"Rows in hourly calendar: {len(data):,}")
    print(f"Complete training examples: {len(model_data):,}")
    print(f"Training examples (evaluation split): {len(train):,}")
    print(f"Held-out later test examples: {len(test):,}")
    print(f"Test period starts: {split_time}")
    print(f"Weather model MAE: {model_mae:.2f} patients per 2-hour forecast")
    print(f"Simple baseline MAE: {baseline_mae:.2f} patients per 2-hour forecast")
    print(f"Saved reusable model: {MODEL_FILE}")
    print("NOTE: dataset-relative demo only; do not use for clinical/staffing decisions.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
