# 🛡️ Iron-Gryph

**Iron-Gryph** is an enterprise-grade platform housing two high-assurance systems:
1. **Legal & Investigation Evidence Vault (`legal_system/`)**: Secure digital evidence repository with **FIPS 180-4 SHA-256 cryptographic integrity seals**, real-time Green/Red tamper detection badges, role-based access control (RBAC), zero-friction persona switching, and an immutable chain-of-custody audit ledger.
2. **Emergency Resource Surge AI (`app/`)**: Intelligent multi-source healthcare demand forecasting combining admission trends, ambulance dispatches, weather telemetry, and bed/staff linear programming optimization.

---

## 🏛️ Legal & Investigation Evidence Vault

### Highlights
- **Zero-Barrier UI & Role Switcher**: Instant switching between `Chief Vance (Administrator)` and `Det. Cole (Investigator)` directly in the header with zero login hurdles.
- **Cryptographic Evidence Seals**:
  - 🛡️ **Verified Green Shield (`VERIFIED_GREEN`)**: Confirms live file on disk matches the authoritative intake SHA-256 hash.
  - ⚠️ **Tampered Crimson Warning (`TAMPERED_RED`)**: Real-time forensic alert if an exhibit has been altered or corrupted.
- **Interactive Tamper Lab**: One-click **Simulate Tamper** and **Restore Seal** to demonstrate tamper detection live in demos and courtroom audits.
- **Browser WebCrypto Ingress**: Computes SHA-256 client-side using `window.crypto.subtle` prior to deposit, verified server-side on arrival.
- **Immutable Chain-of-Custody Ledger**: Complete chronological ledger of every view, download, verification, and tamper alert, with exportable judicial JSON logs.

### Running the Evidence Vault
```bash
# Activate environment
source .venv/bin/activate

# Launch on port 8080
uvicorn legal_system.app.main:app --host 0.0.0.0 --port 8080 --reload
```
- **Web App**: [http://localhost:8080](http://localhost:8080)
- **Interactive Swagger Docs**: [http://localhost:8080/docs](http://localhost:8080/docs)
- **ReDoc Specification**: [http://localhost:8080/redoc](http://localhost:8080/redoc)

---

## 🏥 Hospital Resource & Surge AI

### Highlights
- **Demand Forecasting Engine**: Random Forest and Gradient Boosting models combining weather alerts, regional mass events, incoming ambulances, and historical patient patterns.
- **Resource Allocator**: Linear programming solver allocating available emergency beds, specialized trauma staff, and ambulance dispatches.
- **Automated Surge Alerts**: Real-time triage triggering emergency resource reallocations.

### Running the Surge AI API
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- **Interactive Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🧪 Testing

Comprehensive test suites are included for both systems:
```bash
# Run all automated tests
pytest tests -v
```

---

## 📂 Project Architecture

```
Iron-Gryph/
├── legal_system/               # Legal & Investigation Evidence Vault
│   ├── app/
│   │   ├── routers/            # cases, evidence, audit, auth endpoints
│   │   ├── audit_service.py    # Chain-of-custody immutable logging
│   │   ├── auth.py             # RBAC & header/bearer persona resolution
│   │   ├── config.py           # Settings & paths
│   │   ├── database.py         # SQLAlchemy SQLite engine
│   │   ├── hashing.py          # SHA-256 & disk integrity checking
│   │   ├── models.py           # Database entities
│   │   ├── schemas.py          # Pydantic v2 schemas
│   │   ├── seed.py             # Pre-seeded cases, exhibits, audit records
│   │   └── main.py             # FastAPI entrypoint
│   ├── static/
│   │   ├── index.html          # Modern obsidian zero-login dashboard
│   │   ├── style.css           # Glassmorphic dark styling & badges
│   │   └── app.js              # Client logic & WebCrypto hashing
│   └── README.md               # Legal system & mobile integration guide
├── app/                        # Hospital Surge Prediction & Resource AI
│   ├── api/v1/                 # Endpoints (hospitals, patients, predictions, staff)
│   ├── ml/                     # ML demand forecaster & optimizer
│   ├── models/                 # ORM models
│   ├── schemas/                # Schemas
│   └── services/               # Weather, events, allocations, alerts
├── tests/
│   ├── test_legal_system.py    # 5/5 legal vault tests
│   ├── test_api.py             # Surge API tests
│   └── test_ml.py              # ML pipeline tests
├── requirements.txt            # Python dependencies
└── README.md                   # Repository overview
```
