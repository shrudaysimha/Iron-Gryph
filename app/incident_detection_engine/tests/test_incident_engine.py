import json
import tempfile
import unittest
from pathlib import Path

from incident_engine import EngineConfig, analyze_incidents, analyze_file, haversine_km, load_incidents


HOSPITAL = (12.9716, 77.5946)


def record(i, lat=12.9750, lon=77.6000, time="2026-10-17T18:10:00Z",
           severity=3, weather="none", kind="road_accident"):
    return {
        "incident_id": f"INC-{i}",
        "incident_type": kind,
        "latitude": lat,
        "longitude": lon,
        "timestamp": time,
        "severity": severity,
        "data_source": "SIMULATED_TEST",
        "weather_condition": weather,
    }


class IncidentEngineTests(unittest.TestCase):
    def setUp(self):
        self.config = EngineConfig(*HOSPITAL)

    def test_distance_same_point_is_zero(self):
        self.assertAlmostEqual(haversine_km(*HOSPITAL, *HOSPITAL), 0.0, places=6)

    def test_load_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "incidents.json"
            path.write_text(json.dumps([record(1)]), encoding="utf-8")
            self.assertEqual(len(load_incidents(path)), 1)

    def test_load_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "incidents.csv"
            path.write_text(
                "incident_id,incident_type,latitude,longitude,timestamp,severity,data_source\n"
                "INC-1,road_accident,12.975,77.600,2026-10-17T18:10:00Z,3,SIMULATED\n",
                encoding="utf-8",
            )
            self.assertEqual(len(load_incidents(path)), 1)

    def test_clusters_only_when_near_and_in_time(self):
        data = [
            record(1, time="2026-10-17T18:00:00Z"),
            record(2, lat=12.976, lon=77.601, time="2026-10-17T18:30:00Z"),
            record(3, lat=13.2, lon=77.9, time="2026-10-17T18:20:00Z"),
        ]
        result = analyze_incidents(data, self.config)
        self.assertEqual(len(result["clusters"]), 1)
        self.assertEqual(set(result["clusters"][0]["incident_ids"]), {"INC-1", "INC-2"})

    def test_weather_increases_score(self):
        plain = analyze_incidents([record(1, severity=3)], self.config)["risk"]["risk_score"]
        wet = analyze_incidents([record(1, severity=3, weather="heavy_rain")], self.config)["risk"]["risk_score"]
        self.assertGreater(wet, plain)

    def test_far_incident_is_not_scored(self):
        result = analyze_incidents([record(1, lat=13.5, lon=78.5)], self.config)
        self.assertEqual(result["incident_count_scored"], 0)
        self.assertEqual(result["risk"]["risk_category"], "LOW")

    def test_invalid_severity_rejected(self):
        with self.assertRaises(ValueError):
            analyze_incidents([record(1, severity=7)], self.config)

    def test_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError):
            analyze_incidents([record(1), record(1)], self.config)

    def test_file_analysis_returns_disclaimer(self):
        result = analyze_file(Path(__file__).parents[1] / "sample_incidents.json", self.config)
        self.assertTrue(result["is_simulated_demo"])
        self.assertEqual(result["clinical_validation"], "NOT_VALIDATED")
        self.assertIn("not a clinically validated prediction", result["alert"])


if __name__ == "__main__":
    unittest.main()
