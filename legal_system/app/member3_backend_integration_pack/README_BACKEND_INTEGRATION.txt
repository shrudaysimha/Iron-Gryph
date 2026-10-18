MEMBER 3: BACKEND INTEGRATION STARTER
====================================

PURPOSE
-------
This pack turns the standalone weather prediction script into a reusable model
artifact plus a small FastAPI service that Member 1 can call.

FILES
-----
train_and_save_model.py
  Reads hourly_arrivals_with_weather.csv, evaluates a chronological holdout,
  trains a final model, and saves surge_model.joblib.

api_example.py
  Exposes GET /health and POST /predict/surge endpoints.

REQUIRED EXISTING FILE
----------------------
Keep hourly_arrivals_with_weather.csv in the SAME folder as these two Python
files. It is created by download_align_weather.py.

SETUP IN THE VS CODE TERMINAL
-----------------------------
1. Open the folder containing hourly_arrivals_with_weather.csv.
2. Install packages:
   python -m pip install pandas numpy scikit-learn joblib fastapi uvicorn
3. Train and save the model artifact:
   python train_and_save_model.py
4. Start the prediction API:
   python -m uvicorn api_example:app --reload
5. Open this URL in your browser:
   http://127.0.0.1:8000/docs
6. Select POST /predict/surge, click Try it out, and use this example JSON:

{
  "timestamp": "2017-12-30T23:00:00",
  "arrivals_now": 2,
  "arrivals_1h_ago": 3,
  "arrivals_2h_ago": 2,
  "arrivals_24h_ago": 1,
  "arrivals_168h_ago": 2,
  "temperature_2m": -2.5,
  "relative_humidity_2m": 80,
  "precipitation": 0,
  "wind_speed_10m": 12,
  "weather_code": 3
}

The JSON numbers are illustrative test inputs, not current hospital observations.
Use Execute to get the model's JSON response.

HOW MEMBER 1 CAN CONNECT
------------------------
If Member 1's backend is a separate service, it can POST the required JSON to:
  http://127.0.0.1:8000/predict/surge

Example Python call from the backend:

  import requests
  response = requests.post(
      "http://127.0.0.1:8000/predict/surge",
      json=forecast_input,
      timeout=10,
  )
  response.raise_for_status()
  prediction = response.json()

If the backend runs on another computer, 127.0.0.1 points to that computer,
not your PC. Host the API on a shared reachable machine and use that machine's
address, with appropriate network/security configuration. Do not expose a demo
server publicly without protection.

INPUT CONTRACT
--------------
timestamp: ISO timestamp for the time the prediction is being made
arrivals_now: arrivals in current hour
arrivals_1h_ago: arrivals one hour ago
arrivals_2h_ago: arrivals two hours ago
arrivals_24h_ago: arrivals at the corresponding hour yesterday
arrivals_168h_ago: arrivals at the corresponding hour one week ago
temperature_2m: Celsius
relative_humidity_2m: percent
precipitation: mm/hour
wind_speed_10m: km/hour
weather_code: Open-Meteo WMO weather code

OUTPUT CONTRACT
---------------
The API returns forecast_origin_timestamp, horizon_hours,
predicted_arrivals_next_2h, dataset_relative_demand_level, evaluation metrics,
and data/safety notes. The demand label is based on historical dataset
quantiles, NOT real hospital capacity thresholds.

IMPORTANT LIMITATIONS
---------------------
- The arrival data are historical US research data, not Bengaluru hospital data.
- Des Moines weather is an approximate proxy, not a verified hospital location.
- The illustrative API example uses historical-style values, not live hospital data.
- The model needs the same type and units of features it was trained on.
- The API does not determine bed counts, staff assignments, ambulance deployment,
  triage priority, or clinical decisions. Those belong to separate validated
  decision-support workflows and qualified hospital personnel.
- Do not use this prototype for real clinical, staffing, or emergency decisions.
