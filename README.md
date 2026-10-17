# 🏥 MedCore Surge AI — Hospital Emergency Resource & Surge Allocation Engine
### *Smart India Hackathon (SIH) Solution*

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-teal.svg)](https://fastapi.tiangolo.com/)
[![PuLP-Optimization](https://img.shields.io/badge/PuLP-Linear%20Programming-orange.svg)](https://coin-or.github.io/pulp/)
[![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-Surge%20Forecasting-green.svg)](https://scikit-learn.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📌 Problem Statement

> **"Hospitals can suddenly experience surges in patients due to accidents, disease outbreaks, extreme weather, or mass events. The challenge is not simply predicting the number of patients, but deciding how to allocate limited beds, doctors, ambulances, and emergency resources."**

MedCore Surge AI is an end-to-end clinical intelligence platform combining **6 real-time data feeds** to forecast imminent demand and automatically execute **Linear Programming (LP) resource allocations** to prevent emergency department gridlock.

---

## ⚡ The 6 Integrated Data Feeds

MedCore Surge AI continuously ingests and cross-correlates 6 heterogeneous signals:

| # | Data Stream | Source / Mechanism | Role in Decision Engine |
|---|-------------|--------------------|-------------------------|
| **1** | **Historical Admission Patterns** | Multi-year EHR SQLite / Time-Series | Baseline cyclical demand, seasonal illness curves, day-of-week trends |
| **2** | **Current Emergency Arrivals** | Live Triage Queue (ESI Levels 1–5) | Active emergency department census, acuity breakdown, immediate bed requests |
| **3** | **CAD Ambulance Telemetry** | Computer-Aided Dispatch GPS / In-transit | ETA, trauma severity, automated rerouting & dynamic diversion recommendation |
| **4** | **Available Beds & ICU Capacity** | Census telemetry across 5+ wards | Real-time occupancy, surge expansion limits, step-down bed transitions |
| **5** | **Staff Availability** | Doctor & Nurse Shift Rosters | On-duty counts, on-call reserve activation, patient-to-staff safety ratios |
| **6** | **Local Events & Weather** | MetOffice/NOAA APIs & City Calendar | Extreme heat/cold multipliers, mass gathering surge coefficient |

---

## 🚀 Key Features

### 1. Zero-Friction Emergency Command Center (`static/`)
- **No Login Barriers**: Instant access to the operational dashboard for rapid incident response.
- **Glassmorphic Bento UI**: Modern dashboard with visual hierarchy, micro-animations, and real-time metrics.
- **Multi-Facility Switching**: Switch between City General Hospital (300 beds), Metro Emergency Medical Center (150 beds), and District Public Hospital (80 beds) with a single click.

### 2. Multi-Modal Surge Prediction Engine (`app/ml/`)
- Predicts expected patient intake over 6h, 12h, 24h, and 48h windows.
- Ingests weather severity index (0.8x–2.2x multipliers) and mass gathering proximity factors.
- Outputs confidence intervals, dominant clinical risk drivers, and peak surge timing.

### 3. PuLP Linear Programming Resource Allocation (`app/services/allocation_service.py`)
- Optimizes bed re-allocations (Emergency, ICU, General, Step-Down) while respecting clinical constraints.
- Recommends on-call physician and nurse mobilizations to maintain safe staffing ratios.
- Provides 1-click **Apply Allocation Directives** to immediately update ward allocations in the live database.

### 4. CAD Ambulance Fleet Telemetry & Smart Diversion (`app/api/v1/ambulances.py`)
- Live GPS tracking of active ambulances with real-time ETA calculation.
- Automated hospital diversion recommendations when ED or ICU occupancy exceeds 90% threshold.

### 5. Interactive What-If Scenario Simulator
- Test unexpected mass casualty incidents (MCI), toxic chemical spills, heatwaves, or marathon stampedes.
- Live slider controls to dynamically adjust incoming patient volume (+5 to +100 patients) and weather factors.
- Instant recalculation of bed stress, required on-call doctors, and ambulance diversion recommendations.

---

## 🛠️ Quickstart & Local Setup

### 1. Prerequisites
- Python 3.10+
- SQLite3

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/shrudaysimha/Iron-Gryph.git
cd Iron-Gryph

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Launch the Application
```bash
# Start the unified FastAPI server & Command Center UI
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

- **Emergency Command Center**: Open [http://localhost:8080](http://localhost:8080)
- **Interactive OpenAPI Documentation**: Open [http://localhost:8080/docs](http://localhost:8080/docs)
- **ReDoc API Explorer**: Open [http://localhost:8080/redoc](http://localhost:8080/redoc)

---

## 📊 API Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Emergency Command Center Single-Page App |
| `GET` | `/api/v1/dashboard/overview` | Unified 6-feed dashboard metrics & ward censuses |
| `GET` | `/api/v1/predictions/demand` | 24-hour multi-modal ML surge demand forecast |
| `GET` | `/api/v1/allocations/recommend` | PuLP Linear Programming optimal resource allocations |
| `POST` | `/api/v1/allocations/apply` | Apply LP recommendations to hospital wards & roster |
| `GET` | `/api/v1/ambulances/` | Live CAD ambulance fleet telemetry & diversion statuses |
| `GET` | `/api/v1/environment/weather` | Live weather telemetry & mass event proximity index |
| `GET` | `/api/v1/alerts/` | Active surge alerts & emergency department triggers |
| `POST` | `/api/v1/patients/admit` | Rapid emergency patient triage & bed reservation |

---

## 🧪 Test Suite

Run the comprehensive test suite verifying the ML models, linear programming allocator, and API endpoints:

```bash
pytest tests -v
```

All 20 automated tests pass with 100% test coverage across core allocation modules.

---

## 🏛️ System Architecture

```
Iron-Gryph/
├── static/                     # MedCore Surge AI Emergency Command Center (SPA)
│   ├── index.html              # Bento UI, 6-feed verification, LP directive tables
│   ├── style.css               # Glassmorphism, animations, responsive layout
│   └── app.js                  # Live API sync, simulation engine, 1-click approvals
├── app/                        # Hospital Surge Prediction & Resource AI Engine
│   ├── api/v1/                 # Endpoints (dashboard, allocations, ambulances, alerts)
│   ├── ml/                     # ML demand forecaster & time-series models
│   ├── models/                 # SQLAlchemy ORM models (hospitals, beds, staff, CAD)
│   ├── schemas/                # Pydantic v2 data validation schemas
│   └── services/               # LP allocation optimizer, weather & alerts services
├── tests/                      # Automated test suite (pytest)
│   ├── test_api.py             # API endpoints verification
│   └── test_ml.py              # ML forecasting & LP solver tests
├── hospital_surge.db           # SQLite database pre-seeded with 3 facilities
├── requirements.txt            # Python dependencies
└── README.md                   # Solution documentation
```

---

## 👥 Smart India Hackathon Submission
Built with precision for healthcare emergency resilience. Zero friction, intelligent automation, life-saving resource optimization.
