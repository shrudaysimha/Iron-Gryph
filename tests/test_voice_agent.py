"""
Automated Tests for Voice-Enabled Bed Reservation & Hospital Contact Agent.
"""

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.ml.voice_hospital_agent import ClinicalVoiceAgentModel
from app.models.hospital import Bed

client = TestClient(app)


def test_clinical_voice_model_entity_extraction_stemi():
    """Verify NLP extraction of cardiac arrest / STEMI condition and acuity."""
    model = ClinicalVoiceAgentModel()
    transcript = "Emergency hold! Patient is in acute cardiac arrest and STEMI, reserve ICU bed 102 with ventilator"
    analysis = model.analyze_transcript(transcript)

    assert analysis["acuity_level"] == "ESI-1 (Critical Resuscitation)"
    assert analysis["triage_score"] == 1
    assert analysis["urgency"] == "CRITICAL"
    assert analysis["target_ward_type"] == "icu"
    assert analysis["requires_ventilator"] is True
    assert analysis["requires_oxygen"] is True
    assert "Hamilton G5 Ventilator" in analysis["equipment_needed"]
    assert analysis["extracted_bed_number"] == "ICU-102"


def test_clinical_voice_model_entity_extraction_trauma():
    """Verify extraction of polytrauma, GCS, and inbound ETA."""
    model = ClinicalVoiceAgentModel()
    transcript = "Incoming ambulance with severe polytrauma victim GCS 8, inbound in 6 minutes, need resuscitation bay"
    analysis = model.analyze_transcript(transcript)

    assert analysis["triage_score"] == 1
    assert "Polytrauma" in analysis["patient_condition"]
    assert analysis["eta_minutes"] == 6
    assert analysis["requires_ventilator"] is True


def test_voice_agent_directive_execution_with_profile():
    """Verify end-to-end directive execution, profile auto-enrichment, and DB pessimistic lock."""
    db = SessionLocal()
    try:
        model = ClinicalVoiceAgentModel()
        transcript = "Reserve ICU bed 102 for acute heart attack patient with ventilator support"
        custom_profile = {
            "employee_id": "EMP-1001",
            "name": "Priya Patel, RN",
            "role": "nurse",
            "title": "Head Triage Officer",
            "department": "Emergency Rapid Intake",
            "hospital": "SIDS Hospital Surat",
        }

        result = model.process_voice_directive(
            transcript=transcript,
            hospital_id=1,
            staff_profile=custom_profile,
            db=db,
            explicit_bed="ICU-102",
        )

        assert result["success"] is True
        assert result["verified_staff"]["employee_id"] == "EMP-1001"
        assert result["verified_staff"]["name"] == "Priya Patel, RN"
        assert result["verified_staff"]["verification_status"] == "VERIFIED_ACTIVE"
        assert "speech_feedback" in result
        assert "Hamilton G5" in result["speech_feedback"]

        if result["reservation"]:
            assert result["reservation"]["status"] == "reserved"
            assert result["reservation"]["reservation_token"] is not None
            assert result["reservation"]["ttl_seconds"] == 300
    finally:
        db.close()


def test_api_v1_beds_voice_reserve_endpoint():
    """Test POST /api/v1/beds/voice-reserve endpoint via HTTP TestClient."""
    payload = {
        "audio_transcript": "Emergency hold for acute respiratory failure patient, reserve ICU bed with oxygen and ventilator",
        "hospital_id": 1,
        "staff_profile": {
            "employee_id": "EMP-1005",
            "name": "Dr. Rajiv Mehta",
            "role": "doctor",
            "title": "Chief Trauma Surgeon & Medical Director",
            "department": "Emergency Trauma & Surgical ICU",
            "hospital": "SIDS Hospital Surat",
            "specialization": "Trauma & Critical Care",
        },
        "target_bed_id": "ICU-102",
    }

    response = client.post("/api/v1/beds/voice-reserve", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["model_analysis"]["acuity_level"] == "ESI-1 (Critical Resuscitation)"
    assert data["model_analysis"]["requires_ventilator"] is True
    assert data["verified_staff"]["employee_id"] == "EMP-1005"
    assert data["verified_staff"]["name"] == "Dr. Rajiv Mehta"
    assert len(data["speech_feedback"]) > 10


def test_api_v1_beds_voice_contact_alias():
    """Test POST /api/v1/beds/voice-contact alias endpoint."""
    payload = {
        "audio_transcript": "Contact hospital for incoming acute stroke patient needing emergency admission",
        "hospital_id": 1,
    }

    response = client.post("/api/v1/beds/voice-contact", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    # Default profile auto-bound when omitted
    assert data["verified_staff"]["employee_id"] == "EMP-1005"
    assert "Stroke" in data["model_analysis"]["patient_condition"]


def test_voice_reserve_step_down_monitoring():
    """Test voice booking for step-down post-op observation."""
    payload = {
        "audio_transcript": "Hold step-down bed for post-op observation patient in 10 minutes",
        "hospital_id": 1,
    }

    response = client.post("/api/v1/beds/voice-reserve", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["model_analysis"]["urgency"] == "MODERATE"
    assert data["model_analysis"]["eta_minutes"] == 10
