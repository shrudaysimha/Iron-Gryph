"""Member 3: Hospital arrivals + historical weather prototype.

This script expects hourly_arrivals_with_weather.csv in the same folder.
That CSV is produced by download_align_weather.py.

Important limitations:
- Historical US hospital arrival data; not validated for a Bengaluru hospital.
- Des Moines, Iowa weather is only an approximate proxy for the source hospital.
- Uses weather observed at forecast-origin time t, not a forecast of weather at t+1/t+2.
- Forecasts the combined arrivals during the next two hours (t+1 and t+2).
- Demand labels are data-relative demo labels only, not hospital capacity thresholds.
"""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

DATA_FILE = Path(__file__).with_name("hourly_arrivals_with_weather.csv")
RANDOM_STATE = 42
WEATHER_NUMERIC = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
]
WEATHER_REQUIRED = WEATHER_NUMERIC + ["weather_code"]


def main() -> None:
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Could not find {DATA_FILE.name}. Keep this script in the same folder "
            "as hourly_arrivals_with_weather.csv. First run download_align_weather.py."
        )

    data = pd.read_csv(DATA_FILE, parse_dates=["timestamp"])
    required = {"timestamp", "arrivals", *WEATHER_REQUIRED}
    missing = required - set(data.columns)
    if missing:
        raise ValueError(f"CSV is missing required columns: {sorted(missing)}")

    for col in ["arrivals", *WEATHER_REQUIRED]:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data = data.drop_duplicates("timestamp").set_index("timestamp").sort_index()

    # Reindex to a complete hourly timeline. Missing arrival/weather values stay missing.
    full_index = pd.date_range(data.index.min(), data.index.max(), freq="h")
    data = data.reindex(full_index)
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

    # Weather at the prediction origin time t; no future observed weather is used.
    for col in WEATHER_NUMERIC:
        features[col] = data[col]

    # Weather codes are categories, not continuous measurements, so one-hot encode them.
    code_text = data["weather_code"].round().astype("Int64").astype("string")
    weather_dummies = pd.get_dummies(code_text, prefix="weather_code", dtype=int)
    weather_dummies.index = data.index
    features = pd.concat([features, weather_dummies], axis=1)

    # Ensure rows with missing weather remain incomplete and are excluded from training.
    weather_complete = data[WEATHER_REQUIRED].notna().all(axis=1)
    features.loc[~weather_complete, :] = np.nan

    # Target: sum of arrivals in the next two hours.
    target = arrivals.shift(-1) + arrivals.shift(-2)
    target.name = "arrivals_next_2h"
    model_data = pd.concat([features, target], axis=1).dropna()
    feature_cols = list(features.columns)

    if len(model_data) < 100:
        raise ValueError(
            f"Only {len(model_data)} complete training examples are available. "
            "Check missing data and the weather CSV."
        )

    # Chronological split: training uses earlier timestamps, testing uses later ones.
    split_position = int(len(data) * 0.80)
    split_time = data.index[split_position]
    train_cutoff = split_time - pd.Timedelta(hours=2)
    train = model_data[model_data.index < train_cutoff]
    test = model_data[model_data.index >= split_time]
    if train.empty or test.empty:
        raise ValueError("Not enough complete records for a chronological train/test split.")

    model = RandomForestRegressor(
        n_estimators=250,
        min_samples_leaf=3,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(train[feature_cols], train["arrivals_next_2h"])
    predictions = np.clip(model.predict(test[feature_cols]), 0, None)
    model_mae = mean_absolute_error(test["arrivals_next_2h"], predictions)

    # Same baseline and same held-out rows for a fair comparison.
    baseline = np.clip(test["arrivals_now"] + test["arrivals_1h_ago"], 0, None)
    baseline_mae = mean_absolute_error(test["arrivals_next_2h"], baseline)

    print("\n=== HOSPITAL SURGE PREDICTOR — WEATHER MODEL ===")
    print("Arrival data: historical US research dataset")
    print("Weather data: Des Moines, Iowa (approximate proxy only)")
    print("Weather used: observed weather at forecast-origin time, not future weather")
    print("Not validated for a Bengaluru hospital; do not use for clinical/staffing decisions.")
    print(f"Hourly rows in calendar: {len(data):,}")
    print(f"Complete examples after arrival + weather checks: {len(model_data):,}")
    print(f"Training examples: {len(train):,}")
    print(f"Later held-out test examples: {len(test):,}")
    print(f"Test period starts: {split_time}")
    print(f"Weather model test MAE: {model_mae:.2f} patients per 2-hour forecast")
    print(f"Simple baseline test MAE: {baseline_mae:.2f} patients per 2-hour forecast")

    if model_mae < baseline_mae:
        print("Evaluation note: weather model beat the baseline on this held-out period.")
    else:
        print("Evaluation note: weather model did not beat the baseline on this held-out period.")
        print("Adding weather does not guarantee better forecasts; compare against the no-weather model.")

    # Display highest feature importances as a debugging aid, not as causal evidence.
    importances = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=False)
    print("\nTop 10 feature importances (not evidence of causation):")
    print(importances.head(10).to_string())

    # Refit on all complete examples to make a current-to-dataset-end demo forecast.
    final_model = RandomForestRegressor(
        n_estimators=250,
        min_samples_leaf=3,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    final_model.fit(model_data[feature_cols], model_data["arrivals_next_2h"])
    latest_context = features.dropna().iloc[[-1]]
    forecast_timestamp = latest_context.index[0]
    forecast = max(0, int(round(float(final_model.predict(latest_context[feature_cols])[0]))))

    low_cutoff = float(train["arrivals_next_2h"].quantile(0.50))
    high_cutoff = float(train["arrivals_next_2h"].quantile(0.80))
    if forecast <= low_cutoff:
        level = "LOW"
    elif forecast <= high_cutoff:
        level = "MEDIUM"
    else:
        level = "HIGH"

    print("\n--- DEMO FORECAST ---")
    print(f"Forecast origin timestamp: {forecast_timestamp}")
    print(f"Predicted arrivals in the following 2 hours: {forecast} patients")
    print(f"Dataset-relative demo demand label: {level}")
    print("Demand cutoffs come from the historical training data, not hospital capacity.")
    print("The forecast is a historical-data demo, not a live forecast for today.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
