# ⚖️ IronGryph Legal & Investigation Document Management System

A secure, enterprise-grade digital evidence repository and legal case management platform featuring **FIPS 180-4 compliant SHA-256 cryptographic verification**, **Role-Based Access Control (RBAC)**, and an **immutable chain-of-custody audit ledger**.

---

## 🌟 Key Features

1. **Role-Based Access Control (RBAC):**
   - **Administrator (Chief Elena Vance):** Full system access, audit trail surveillance, tamper alarms, and forensic data exports.
   - **Investigator (Detective Marcus Cole / Dr. Sarah Chen):** Case intake, evidence exhibit deposits, hash verification, and case lifecycle updates.
2. **Case Dashboard (Screen 2):**
   - High-acuity case management cards with priority tags (Critical, High, Medium, Low), classification filters (Financial Fraud, Cybercrime, Narcotics, Public Corruption), and live search.
3. **Case Detail & Evidence Vault (Screen 3):**
   - Exhibit metadata and physical storage tracking.
   - **Green Shield Badge (`VERIFIED_GREEN`)**: Real-time validation confirming that the on-disk evidence file matches the immutable intake SHA-256 digest.
   - **Red Warning Badge (`TAMPERED_RED`)**: Instant cryptographic alarm if file content has been altered or corrupted.
   - Interactive **"Simulate Tamper"** and **"Restore Seal"** demonstration buttons.
4. **Evidence Ingress & WebCrypto Hashing (Screen 4):**
   - Drag-and-drop file upload with live client-side SHA-256 preview using the browser's native `window.crypto.subtle` API before transmission, verified server-side upon storage.
5. **Chain-of-Custody Audit Ledger (Screen 5 - Admin Only):**
   - Immutable audit trail recording every access, login, view, download, verification, and tamper alert with exact UTC timestamps, user badges, and SHA-256 snapshots.
   - Judicial JSON export capability.

---

## 🚀 Quick Start

### 1. Launch Server
```bash
# Activate virtual environment
source .venv/bin/activate

# Start server on port 8080
uvicorn legal_system.app.main:app --host 0.0.0.0 --port 8080 --reload
```

- **Interactive Web App & Mobile UI:** [http://localhost:8080](http://localhost:8080)
- **Interactive Swagger API Docs:** [http://localhost:8080/docs](http://localhost:8080/docs)
- **ReDoc Specification:** [http://localhost:8080/redoc](http://localhost:8080/redoc)

---

## 🔑 Demo Credentials

| Role | Username | Password | Badge Number | Permissions |
|------|----------|----------|--------------|-------------|
| **Administrator** | `admin` | `admin123` | `ADM-001` | Full Access, Audit Ledger, Tamper Alarms |
| **Lead Detective** | `mcole` | `investigator123` | `INV-401` | Cases, Evidence Deposit, Hash Verification |
| **Forensic Specialist** | `schen` | `investigator123` | `INV-508` | Cases, Evidence Deposit, Cyber Artifacts |

*(You can also use the one-click role buttons on the login terminal for instant switching.)*

---

## 📱 Mobile App (React Native / Flutter) Integration Guide

If connecting a Flutter or React Native mobile client (e.g. from the Soft UI React Native or Flutter UI templates):

### Screen Mapping to API Endpoints

1. **Screen 1 (Auth & Role Check):**
   - `POST /api/v1/auth/login` → Store `access_token` and inspect `role` field (`administrator` vs `investigator`).
2. **Screen 2 (Case Dashboard):**
   - `GET /api/v1/cases/?status=Open&search=...` → Populate case card grid.
3. **Screen 3 (Case Detail & Evidence Vault):**
   - `GET /api/v1/cases/{id}` → List exhibits.
   - `POST /api/v1/evidence/{id}/verify` → Check hash and render Green Shield (`is_valid: true`) or Red Warning (`is_valid: false`).
4. **Screen 4 (Upload Modal):**
   - `POST /api/v1/evidence/upload` (`multipart/form-data`).
5. **Screen 5 (Audit Log - Admin Only):**
   - `GET /api/v1/audit/` → Render chronological timeline or data table.
