"""
Unit tests for risk scoring and alert generation.

Tests verify:
  - Empty incidents → LOW / zero score.
  - Weather presence increases score.
  - More incidents increase score.
  - Higher severity increases score.
  - Proximity affects score.
  - Category boundaries (LOW / MODERATE / HIGH).
  - Alert generation produces required fields.
"""
import pytest

from app.risk_scoring import generate_alert, score_risk, SEVERE_WEATHER_CONDITIONS


def _scored_inc(dist=1.0, sev=3, weather="none"):
    """Quick incident for scoring tests (must already have distance_km)."""
    return {
        "incident_id": f"INC-{id(_scored_inc)}",
        "distance_km": dist,
        "severity": sev,
        "weather_condition": weather,
    }


class TestScoreRisk:
    def test_empty_incidents_gives_low(self):
        result = score_risk([])
        assert result["risk_score"] == 0.0
        assert result["risk_category"] == "LOW"

    def test_single_mild_incident_is_low(self):
        result = score_risk([_scored_inc(dist=14.0, sev=1)])
        assert result["risk_category"] == "LOW"

    def test_weather_increases_score(self):
        plain = score_risk([_scored_inc(sev=3)])["risk_score"]
        wet = score_risk([_scored_inc(sev=3, weather="heavy_rain")])["risk_score"]
        assert wet > plain

    def test_more_incidents_increase_score(self):
        one = score_risk([_scored_inc()])["risk_score"]
        three = score_risk([_scored_inc(), _scored_inc(), _scored_inc()])["risk_score"]
        assert three > one

    def test_higher_severity_increases_score(self):
        low = score_risk([_scored_inc(sev=1)])["risk_score"]
        high = score_risk([_scored_inc(sev=5)])["risk_score"]
        assert high > low

    def test_closer_proximity_increases_score(self):
        far = score_risk([_scored_inc(dist=14.0)])["risk_score"]
        near = score_risk([_scored_inc(dist=0.5)])["risk_score"]
        assert near > far

    def test_high_risk_category(self):
        # 3+ incidents, high severity, weather, close proximity → HIGH
        incidents = [
            _scored_inc(dist=0.5, sev=5, weather="storm"),
            _scored_inc(dist=1.0, sev=4, weather="heavy_rain"),
            _scored_inc(dist=2.0, sev=4, weather="heavy_rain"),
        ]
        result = score_risk(incidents)
        assert result["risk_category"] == "HIGH"
        assert result["risk_score"] >= 70.0

    def test_score_clamped_to_100(self):
        # Even with extreme inputs, score should not exceed 100
        incidents = [_scored_inc(dist=0.0, sev=5, weather="storm") for _ in range(10)]
        result = score_risk(incidents)
        assert result["risk_score"] <= 100.0

    def test_factors_present(self):
        result = score_risk([_scored_inc()])
        factors = result["factors"]
        assert "incident_count" in factors
        assert "count_factor" in factors
        assert "average_severity" in factors
        assert "nearest_distance_km" in factors
        assert "weather_signal_present" in factors

    def test_reasons_are_human_readable(self):
        result = score_risk([_scored_inc(sev=3, weather="storm")])
        assert len(result["reasons"]) == 4
        assert all(isinstance(r, str) for r in result["reasons"])


class TestGenerateAlert:
    def test_alert_has_required_fields(self):
        risk = score_risk([_scored_inc(sev=3, weather="heavy_rain")])
        alert = generate_alert(risk, [["INC-1", "INC-2"]], [_scored_inc()])
        assert "alert_id" in alert
        assert "timestamp" in alert
        assert "risk_category" in alert
        assert "risk_score" in alert
        assert "alert_message" in alert
        assert "hospital" in alert

    def test_alert_id_format(self):
        risk = score_risk([_scored_inc()])
        alert = generate_alert(risk, [], [])
        assert alert["alert_id"].startswith("ALERT-")

    def test_alert_message_contains_disclaimer(self):
        risk = score_risk([_scored_inc()])
        alert = generate_alert(risk, [], [])
        assert "not a clinically validated prediction" in alert["alert_message"]
