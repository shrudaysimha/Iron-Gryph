# Member 4 — Incident Detection Engine (Demo)

Python standard-library-only demonstration module for a Hospital Patient Surge Prediction System.

**Safety and validity:** All included records are simulated. The scoring formula and thresholds are illustrative and NOT clinically validated. A risk category is an operational signal, not a prediction that a surge will occur.

## Files
- `incident_engine.py` — CSV/JSON loading, validation, distance, clustering, scoring, alert generation, CLI.
- `sample_incidents.json`, `sample_incidents.csv` — same four simulated records.
- `tests/test_incident_engine.py` — unit tests.

## Requirements
Python 3.10+; no third-party packages.

## Run
```bash
python incident_engine.py sample_incidents.json
python incident_engine.py sample_incidents.csv --hospital-lat 12.9716 --hospital-lon 77.5946
python incident_engine.py sample_incidents.json --output analysis.json
```

Run tests from this directory:
```bash
python -m unittest discover -s tests -v
```

## Input schema
Required fields:
- `incident_id`: unique string within the batch
- `incident_type`: e.g. `road_accident`, `storm_report`, `public_gathering`
- `latitude`: decimal degrees, -90..90
- `longitude`: decimal degrees, -180..180
- `timestamp`: ISO-8601; timezone-naive timestamps are interpreted as UTC
- `severity`: integer 1..5 (demo scale; define this consistently for real sources)
- `data_source`: source label

Optional:
- `weather_condition`: `none`, `heavy_rain`, `extreme_heat`, `storm`, `flood`, or another label

JSON may be a list of records or `{"incidents": [...]}`. CSV requires a header row.

## Demonstration scoring rules
Only incidents within `nearby_radius_km` of the hospital contribute to the risk score. All records are still returned with distances.

`score = count_weight × count_factor + severity_weight × severity_factor + proximity_weight × proximity_factor + weather_weight × weather_factor`

Default weights sum to 100:
- Count (35): factor is `min(incident_count / 3, 1)`.
- Severity (30): `(average_severity - 1) / 4`, clamped implicitly by validation to 0..1.
- Proximity (20): `clamp(1 - nearest_distance_km / nearby_radius_km, 0, 1)`.
- Weather (15): 1 if any scored incident has heavy rain, extreme heat, storm or flood; otherwise 0.
- Score is clamped to 0..100.
- LOW: score < 35; MODERATE: 35 to < 70; HIGH: >= 70.

Clustering is a connected-component grouping: two incidents are linked if both distance <= `cluster_radius_km` and absolute timestamp difference <= `cluster_window_minutes`. Chains may create a cluster whose endpoints are farther apart than the radius; change the algorithm if your product needs stricter all-pairs clusters.

## Output contract
Top-level fields:
- `engine`, `is_simulated_demo`, `clinical_validation`
- `hospital`, `configuration`
- `incident_count_total`, `incident_count_scored`
- `clusters`: list of `{cluster_id, incident_ids}`
- `incidents`: each source record plus `distance_km`, normalized UTC `timestamp`, `cluster_id`
- `risk`: `{risk_score, risk_category, reasons, factors}`
- `alert`: human-readable explanation

## Integration notes
Keep this as an isolated module until the team repository is inspected. For a backend integration, call `analyze_file(path, config)` or `analyze_incidents(records, config)` from the existing service layer. Do not add routes or modify shared files until the team's API framework and ownership boundaries are confirmed. Treat real external API feeds as untrusted input and validate them before analysis.
