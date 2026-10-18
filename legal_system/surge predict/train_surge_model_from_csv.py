"""
Hospital Surge Predictor — Member 3 starter using the cleaned hourly arrivals CSV.

Important:
- This is a research/demo model, not a clinically validated hospital forecast.
- It estimates the total arrivals in the TWO HOURS AFTER the input timestamp.
- Blank arrival counts in the CSV mean the source day/hour was missing; they are not zero.
- Demand labels are dataset-relative demonstration labels only.
"""

from pathlib import Path
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

DATA_FILE = Path(__file__).with_name("hourly_arrivals_cleaned.csv")
RANDOM_STATE = 42


def main():
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Could not find {DATA_FILE.name}. Keep this script and the CSV in the same folder."
        )

    data = pd.read_csv(DATA_FILE, parse_dates=["timestamp"])
    required = {"timestamp", "arrivals"}
    missing_columns = required - set(data.columns)
    if missing_columns:
        raise ValueError(f"CSV is missing required columns: {sorted(missing_columns)}")

    data = data[["timestamp", "arrivals"]].copy()
    data["arrivals"] = pd.to_numeric(data["arrivals"], errors="coerce")
    data = data.drop_duplicates("timestamp").set_index("timestamp").sort_index()

    # Reindex to a full hourly timeline so a missing hour/day stays NaN.
    # Never silently fill missing days with zero.
    full_index = pd.date_range(data.index.min(), data.index.max(), freq="h")
    data = data.reindex(full_index)
    arrivals = data["arrivals"].astype(float)

    # Features available at timestamp t.
    features = pd.DataFrame(index=data.index)
    features["hour"] = data.index.hour
    features["day_of_week"] = data.index.dayofweek
    features["month"] = data.index.month
    features["arrivals_now"] = arrivals
    features["arrivals_1h_ago"] = arrivals.shift(1)
    features["arrivals_2h_ago"] = arrivals.shift(2)
    features["arrivals_24h_ago"] = arrivals.shift(24)
    features["arrivals_168h_ago"] = arrivals.shift(168)

    # Target: combined arrivals at t+1 hour and t+2 hours.
    target = arrivals.shift(-1) + arrivals.shift(-2)
    target.name = "arrivals_next_2h"

    model_data = pd.concat([features, target], axis=1).dropna()
    feature_cols = list(features.columns)

    if len(model_data) < 100:
        raise ValueError(
            f"Only {len(model_data)} complete training examples were found. "
            "Check whether the CSV was copied correctly."
        )

    # Chronological holdout: train on earlier dates, test on later dates.
    split_position = int(len(data) * 0.80)
    split_time = data.index[split_position]
    train_cutoff = split_time - pd.Timedelta(hours=2)
    train = model_data[model_data.index < train_cutoff]
    test = model_data[model_data.index >= split_time]

    if train.empty or test.empty:
        raise ValueError("Not enough complete records for a chronological train/test split.")

    eval_model = RandomForestRegressor(
        n_estimators=250,
        min_samples_leaf=3,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    eval_model.fit(train[feature_cols], train["arrivals_next_2h"])
    test_predictions = eval_model.predict(test[feature_cols]).clip(min=0)
    model_mae = mean_absolute_error(test["arrivals_next_2h"], test_predictions)

    # Simple baseline: assume the next two hours will resemble the previous two hours.
    baseline_predictions = (
        test["arrivals_now"] + test["arrivals_1h_ago"]
    ).clip(lower=0)
    baseline_mae = mean_absolute_error(test["arrivals_next_2h"], baseline_predictions)

    print("\n=== HOSPITAL SURGE PREDICTOR — MEMBER 3 ===")
    print("Source: cleaned hourly counts reconstructed from the supplied pivot table")
    print("Reminder: historical US hospital data; not validated for a Bengaluru hospital.")
    print(f"Hourly rows in calendar: {len(data):,}")
    print(f"Complete training examples: {len(model_data):,}")
    print(f"Training examples: {len(train):,}")
    print(f"Later held-out test examples: {len(test):,}")
    print(f"Test period starts: {split_time}")
    print(f"Random Forest test MAE: {model_mae:.2f} patients per 2-hour forecast")
    print(f"Simple baseline test MAE: {baseline_mae:.2f} patients per 2-hour forecast")

    if model_mae < baseline_mae:
        print("Evaluation note: the model outperformed this simple baseline on the held-out period.")
    else:
        print("Evaluation note: the model did not beat this simple baseline on the held-out period.")
        print("Try a simpler time-series model or improve the data before claiming a gain.")

    # Refit on all complete historical examples for the final demo forecast.
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

    # Data-relative tiers only; real operational thresholds must be defined with hospital staff.
    low_cutoff = float(train["arrivals_next_2h"].quantile(0.50))
    high_cutoff = float(train["arrivals_next_2h"].quantile(0.80))
    if forecast <= low_cutoff:
        level = "LOW"
    elif forecast <= high_cutoff:
        level = "MEDIUM"
    else:
        level = "HIGH"

    print("\n--- DEMO FORECAST ---")
    print(f"Forecast made from latest complete context timestamp: {forecast_timestamp}")
    print(f"Predicted arrivals in the following 2 hours: {forecast} patients")
    print(f"Dataset-relative demo demand label: {level}")
    print("Warning: LOW/MEDIUM/HIGH cutoffs are based on this dataset, not hospital capacity.")
    print("Do not use this prototype for real clinical or staffing decisions.")


if __name__ == "__main__":
    main()
