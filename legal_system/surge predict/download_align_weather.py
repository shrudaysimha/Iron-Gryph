"""Download historical weather from Open-Meteo and align it with hourly arrivals.

For hackathon demonstration only:
- Des Moines, Iowa is an approximate proxy, not the verified hospital location.
- Arrival timestamps are treated as local wall-clock time in America/Chicago.
- Missing arrival/weather values are preserved; this script does not invent data.
"""

from pathlib import Path
import sys

import pandas as pd
import requests

# Keep this script in the same folder as hourly_arrivals_cleaned.csv.
FOLDER = Path(__file__).resolve().parent
ARRIVALS_FILE = FOLDER / "hourly_arrivals_cleaned.csv"
OUTPUT_FILE = FOLDER / "hourly_arrivals_with_weather.csv"

# Approximate Des Moines, Iowa coordinates. These are a proxy only.
LATITUDE = 41.5868
LONGITUDE = -93.6250
TIMEZONE = "America/Chicago"
API_URL = "https://archive-api.open-meteo.com/v1/archive"

HOURLY_VARIABLES = [
    "temperature_2m",       # degrees Celsius
    "relative_humidity_2m", # percent
    "precipitation",        # millimeters in the preceding hour
    "weather_code",         # WMO weather code
    "wind_speed_10m",       # km/h
]


def main() -> None:
    if not ARRIVALS_FILE.exists():
        raise FileNotFoundError(
            f"Could not find {ARRIVALS_FILE.name}.\n"
            f"Put this script in the same folder as hourly_arrivals_cleaned.csv.\n"
            f"Current folder: {FOLDER}"
        )

    # 1. Load the cleaned hospital-arrival time series.
    arrivals = pd.read_csv(ARRIVALS_FILE, parse_dates=["timestamp"])
    if not {"timestamp", "arrivals"}.issubset(arrivals.columns):
        raise ValueError(
            "The CSV must contain at least these columns: timestamp, arrivals"
        )

    arrivals["arrivals"] = pd.to_numeric(arrivals["arrivals"], errors="coerce")
    arrivals = arrivals.sort_values("timestamp").drop_duplicates("timestamp")
    start_date = arrivals["timestamp"].min().date().isoformat()
    end_date = arrivals["timestamp"].max().date().isoformat()

    print("=== OPEN-METEO HISTORICAL WEATHER DOWNLOAD ===")
    print("Weather location: Des Moines, Iowa (approximate proxy)")
    print(f"Arrival data period: {start_date} to {end_date}")
    print("Downloading hourly weather data... this may take a moment.")

    # 2. Request historical hourly weather for the same date range.
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(HOURLY_VARIABLES),
        "timezone": TIMEZONE,
        "temperature_unit": "celsius",
        "precipitation_unit": "mm",
        "wind_speed_unit": "kmh",
        # ERA5 provides a consistent historical model for this demo period.
        "models": "era5",
    }

    try:
        response = requests.get(API_URL, params=params, timeout=90)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise RuntimeError(
            "Could not download weather data. Check your internet connection and try again.\n"
            f"Technical detail: {exc}"
        ) from exc

    if payload.get("error"):
        raise RuntimeError(f"Open-Meteo returned an error: {payload.get('reason', payload)}")
    if "hourly" not in payload or "time" not in payload["hourly"]:
        raise RuntimeError(f"Unexpected response from Open-Meteo: {payload}")

    weather = pd.DataFrame(payload["hourly"])
    weather = weather.rename(columns={"time": "timestamp"})
    weather["timestamp"] = pd.to_datetime(weather["timestamp"])

    # 3. Daylight-saving time can produce a repeated local clock hour in autumn.
    # Aggregate repeated local timestamps so the weather table has one row per
    # wall-clock timestamp. Precipitation is summed; other numeric weather
    # values are averaged, and weather_code uses the maximum code.
    if weather["timestamp"].duplicated().any():
        aggregation = {
            "temperature_2m": "mean",
            "relative_humidity_2m": "mean",
            "precipitation": "sum",
            "weather_code": "max",
            "wind_speed_10m": "mean",
        }
        weather = weather.groupby("timestamp", as_index=False).agg(aggregation)

    # 4. Left-join weather onto the arrivals timeline. Every arrivals row stays.
    merged = arrivals.merge(weather, on="timestamp", how="left", validate="one_to_one")
    merged = merged.sort_values("timestamp")

    # 5. Save beside the source files.
    merged.to_csv(OUTPUT_FILE, index=False)

    weather_cols = HOURLY_VARIABLES
    missing_counts = merged[weather_cols].isna().sum()
    matched = merged["temperature_2m"].notna().sum()

    print("\n=== FINISHED ===")
    print(f"Saved file: {OUTPUT_FILE}")
    print(f"Arrival rows preserved: {len(merged):,}")
    print(f"Rows with matched temperature: {matched:,} / {len(merged):,}")
    print("Missing weather values by column:")
    print(missing_counts.to_string())
    print("\nFirst 5 rows:")
    print(merged.head().to_string(index=False))
    print("\nWeather columns and units:")
    print("temperature_2m: °C; relative_humidity_2m: %; precipitation: mm/hour;")
    print("weather_code: WMO code; wind_speed_10m: km/h")
    print("\nIMPORTANT: Des Moines is an approximate proxy, not the verified hospital location.")
    print("Do not use this demo for clinical, staffing, or real-time emergency decisions.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\nERROR: {error}", file=sys.stderr)
        sys.exit(1)
