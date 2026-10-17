"""
Automated Integration Tests for Legal & Investigation Document Management System.

Tests:
1. Authentication & JWT Tokens
2. Role-Based Access Control (Admin vs. Investigator)
3. Case Management & Retrieval
4. Evidence Upload & Cryptographic SHA-256 Hashing
5. Integrity Verification (Green Shield)
6. Tamper Simulation (Red Warning Shield)
7. Canonical Restoration
8. Audit Trail Ledger Enforcement
"""

import io
import pytest
from fastapi.testclient import TestClient

from legal_system.app.main import app
from legal_system.app.seed import seed_legal_data

# Ensure DB is seeded
seed_legal_data()

client = TestClient(app)


def get_token(username, password):
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_auth_and_rbac():
    # Admin Login
    admin_token = get_token("admin", "admin123")
    assert admin_token is not None

    # Investigator Login
    inv_token = get_token("mcole", "investigator123")
    assert inv_token is not None

    # Bad credentials
    bad_res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrongpassword"})
    assert bad_res.status_code == 401

    # Verify Profile
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert me_res.status_code == 200
    assert me_res.json()["role"] == "administrator"

    me_inv = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {inv_token}"})
    assert me_inv.status_code == 200
    assert me_inv.json()["role"] == "investigator"


def test_role_based_access_restriction_on_audit():
    admin_token = get_token("admin", "admin123")
    inv_token = get_token("mcole", "investigator123")

    # Investigator tries to access audit ledger -> Must be 403 Forbidden!
    forbidden_res = client.get("/api/v1/audit/", headers={"Authorization": f"Bearer {inv_token}"})
    assert forbidden_res.status_code == 403

    # Admin access -> Must be 200 OK!
    allowed_res = client.get("/api/v1/audit/", headers={"Authorization": f"Bearer {admin_token}"})
    assert allowed_res.status_code == 200
    assert len(allowed_res.json()) >= 1


def test_case_management():
    inv_token = get_token("mcole", "investigator123")

    # List cases
    cases_res = client.get("/api/v1/cases/", headers={"Authorization": f"Bearer {inv_token}"})
    assert cases_res.status_code == 200
    cases = cases_res.json()
    assert len(cases) >= 1

    # Create new case
    new_case_payload = {
        "title": "Operation Nightshade: Offshore Asset Forgery",
        "description": "Seizure of illicit shell company account records",
        "category": "Financial Fraud",
        "priority": "High"
    }
    create_res = client.post(
        "/api/v1/cases/",
        headers={"Authorization": f"Bearer {inv_token}"},
        json=new_case_payload
    )
    assert create_res.status_code == 201
    created_case = create_res.json()
    assert created_case["case_number"].startswith("CASE-")
    assert created_case["title"] == new_case_payload["title"]

    # Retrieve case details
    detail_res = client.get(
        f"/api/v1/cases/{created_case['id']}",
        headers={"Authorization": f"Bearer {inv_token}"}
    )
    assert detail_res.status_code == 200
    assert "evidence_documents" in detail_res.json()


def test_evidence_upload_and_sha256_verification():
    inv_token = get_token("mcole", "investigator123")

    # Get a case
    cases_res = client.get("/api/v1/cases/", headers={"Authorization": f"Bearer {inv_token}"})
    case_id = cases_res.json()[0]["id"]

    # Upload evidence file
    file_content = b"CRITICAL FORENSIC REPORT: Digital Evidence Exhibit #4492A - Authenticated by Dr. Sarah Chen"
    files = {
        "file": ("forensic_digital_analysis_4492a.txt", io.BytesIO(file_content), "text/plain")
    }
    data = {
        "case_id": case_id,
        "title": "Digital Memory Analysis Exhibit 4492A",
        "category": "Forensic Report",
        "description": "Authenticated forensic extract"
    }

    upload_res = client.post(
        "/api/v1/evidence/upload",
        headers={"Authorization": f"Bearer {inv_token}"},
        data=data,
        files=files
    )
    assert upload_res.status_code == 201
    doc = upload_res.json()
    assert doc["sha256_hash"] is not None
    assert len(doc["sha256_hash"]) == 64  # Valid 64-char hex SHA-256
    evidence_id = doc["id"]

    # Verify initial integrity -> Must be VERIFIED_GREEN
    verify_res = client.post(
        f"/api/v1/evidence/{evidence_id}/verify",
        headers={"Authorization": f"Bearer {inv_token}"}
    )
    assert verify_res.status_code == 200
    verify_data = verify_res.json()
    assert verify_data["is_valid"] is True
    assert verify_data["status_badge"] == "VERIFIED_GREEN"

    # Simulate Tampering -> Must trigger TAMPERED_RED
    tamper_res = client.post(
        f"/api/v1/evidence/{evidence_id}/simulate-tamper",
        headers={"Authorization": f"Bearer {inv_token}"}
    )
    assert tamper_res.status_code == 200
    tamper_data = tamper_res.json()
    assert tamper_data["is_valid"] is False
    assert tamper_data["status_badge"] == "TAMPERED_RED"

    # Restore Canonical State -> Returns to VERIFIED_GREEN
    restore_res = client.post(
        f"/api/v1/evidence/{evidence_id}/restore",
        headers={"Authorization": f"Bearer {inv_token}"}
    )
    assert restore_res.status_code == 200
    restore_data = restore_res.json()
    assert restore_data["is_valid"] is True
    assert restore_data["status_badge"] == "VERIFIED_GREEN"


def test_audit_log_chain_of_custody():
    admin_token = get_token("admin", "admin123")

    audit_res = client.get("/api/v1/audit/", headers={"Authorization": f"Bearer {admin_token}"})
    assert audit_res.status_code == 200
    logs = audit_res.json()
    actions = [l["action"] for l in logs]

    assert "LOGIN_SUCCESS" in actions
    assert "UPLOAD_EVIDENCE" in actions or "VERIFY_HASH_VALID" in actions
