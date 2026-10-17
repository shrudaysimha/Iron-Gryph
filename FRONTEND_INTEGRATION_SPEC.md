# Hospital Surge AI — Frontend Integration Specification (For Stitch)

This document provides complete architectural specifications, API catalogs, TypeScript models, WebSocket protocols, and component blueprints for building the frontend using **Stitch** or any modern web framework.

---

## 1. System Overview & Problem Statement

**Hospital Surge AI** is an emergency healthcare intelligence engine designed to solve hospital bed crises, resource allocation failures, and sudden patient demand surges during crises, mass-casualty events, and epidemic spikes.

### Key Capabilities
1. **Demand Surge Forecasting**: ML models predicting patient arrival volume 1 to 24 hours in advance based on historical hospital load, weather anomalies (heatwaves, cold snaps), and mass gatherings.
2. **Linear Programming Resource Allocation**: Mathematical optimization recommending reallocation of ICU beds, emergency doctors, triage nurses, and ambulance fleet.
3. **Bed Reservation & Concurrency Safety ("The 100-User Problem")**:
   - When 100 users / triage coordinators click "Book Now" simultaneously on the exact same bed:
   - Uses **pessimistic row locking** (`SELECT ... FOR UPDATE` / serializable transaction).
   - Only the first request succeeds; acquires a 5-minute TTL reservation token.
   - The other 99 requests immediately receive `409 Conflict` with `queue_position` and intelligent alternative bed recommendations in the same ward.
4. **Real-time Alert Broadcasts**: WebSocket stream pushing severity alerts (`critical`, `warning`, `info`) to all triage desks and coordinators.
5. **Ambulance Telemetry Tracking**: Real-time vehicle telemetry, ETA, patient condition, oxygen support, and hospital routing.
6. **Legal Evidence Vault**: Cryptographic SHA-256 evidence vault with audit trail for medicolegal compliance, incident logs, and tamper detection.

---

## 2. API Endpoints Catalog

Base URL: `http://localhost:8000` (or `http://localhost:8080`)
OpenAPI Specification: `/openapi.json`
Swagger Documentation: `/docs`
ReDoc Documentation: `/redoc`

### A. System & Health
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Root info listing all active modules |
| `GET` | `/health` | Health check (db connection status, active websockets) |
| `GET` | `/api/info` | API metadata and endpoint directory |

### B. Hospitals & Capacity
| Method | Endpoint | Query / Path Params | Description |
|---|---|---|---|
| `GET` | `/api/v1/hospitals/` | `skip=0`, `limit=100` | List all hospitals in the network |
| `GET` | `/api/v1/hospitals/{id}` | `hospital_id` | Hospital details |
| `GET` | `/api/v1/hospitals/{id}/capacity` | `hospital_id` | Real-time capacity (total, available, ICU, occupancy %) |

### C. Live Bed Grid & Concurrency Reservation (Crucial for Stitch)
| Method | Endpoint | Parameters / Body | Description |
|---|---|---|---|
| `GET` | `/api/v1/beds/grid` | `hospital_id` (query) | Full bed matrix: all wards, all beds, live statuses (`available`, `reserved`, `occupied`, `maintenance`) |
| `POST` | `/api/v1/beds/reserve` | JSON: `{ bed_id, hospital_id, patient_name, triage_score }` | Atomically reserve a bed. Returns reservation token + 5-min TTL or 409 Conflict with alternative beds |
| `POST` | `/api/v1/beds/confirm` | `bed_id` (query), `reservation_token` (query) | Finalize admission: transitions bed from `reserved` to `occupied` |
| `POST` | `/api/v1/beds/release` | `bed_id` (query), `reservation_token` (query) | Release reservation: returns bed from `reserved` to `available` |

### D. Dashboard Overview
| Method | Endpoint | Query Params | Description |
|---|---|---|---|
| `GET` | `/api/v1/dashboard/overview` | `hospital_id=1` | Aggregated command center data: capacity, staff on duty, ambulance fleet, active alerts, recent predictions |

### E. AI Predictions & What-If Simulation
| Method | Endpoint | Parameters / Body | Description |
|---|---|---|---|
| `GET` | `/api/v1/predictions/demand` | `hospital_id=1`, `horizon_hours=24` | Latest demand forecasts with confidence scores |
| `POST` | `/api/v1/predictions/generate` | JSON: `{ hospital_id: 1, horizon_hours: 4 }` | Run ML demand prediction pipeline |

### F. Resource Allocation (Linear Programming)
| Method | Endpoint | Query Params | Description |
|---|---|---|---|
| `GET` | `/api/v1/allocations/recommend` | `hospital_id=1` | Mathematical resource reallocation recommendations with risk levels |
| `POST` | `/api/v1/allocations/implement/{id}` | `allocation_id` | Mark allocation plan as implemented |

### G. Patients & Triage
| Method | Endpoint | Query Params | Description |
|---|---|---|---|
| `GET` | `/api/v1/patients/current` | `hospital_id=1` | Currently admitted patients with triage scores |
| `GET` | `/api/v1/patients/queue` | `hospital_id=1` | Waiting queue ordered by triage urgency (Scores 1 to 5) |
| `POST` | `/api/v1/patients/admit` | JSON patient model | Admit new patient |

### H. Staff on Duty
| Method | Endpoint | Query Params | Description |
|---|---|---|---|
| `GET` | `/api/v1/staff/on-duty` | `hospital_id=1` | Doctors, nurses, and technicians currently on shift |

### I. Ambulance Fleet Telemetry
| Method | Endpoint | Query Params | Description |
|---|---|---|---|
| `GET` | `/api/v1/ambulances/` | `hospital_id=1` | Active ambulances: status, location lat/lng, patient acuity, ETA |

### J. Weather & Events Context
| Method | Endpoint | Query Params | Description |
|---|---|---|---|
| `GET` | `/api/v1/environment/weather` | None | Real-time weather, heat index, and surge risk factor |
| `GET` | `/api/v1/environment/events` | `hospital_id=1` | Local mass gathering events and demand multiplier |

### K. Real-Time Alerts
| Method | Endpoint | Query Params | Description |
|---|---|---|---|
| `GET` | `/api/v1/alerts/` | `hospital_id=1`, `unacknowledged_only=true` | List active emergency alerts |
| `POST` | `/api/v1/alerts/{id}/acknowledge` | `alert_id` | Acknowledge alert |

### L. WebSocket Real-Time Alert Streams
| Protocol | Endpoint | Description |
|---|---|---|
| `WS` | `/ws/alerts` | Global stream for all hospitals |
| `WS` | `/ws/alerts/{hospital_id}` | Filtered stream for specific hospital |

---

## 3. TypeScript Interfaces for Stitch

```typescript
// --- Hospitals & Capacity ---
export interface Hospital {
  id: number;
  name: string;
  address: string;
  city: string;
  state: string;
  latitude: number;
  longitude: number;
  phone: string;
  total_beds: number;
  icu_beds: number;
  emergency_beds: number;
  ventilator_beds: number;
  tier: number;
  is_active: boolean;
}

export interface HospitalCapacity {
  hospital_id: number;
  total_beds: number;
  available_beds: number;
  occupied_beds: number;
  occupancy_rate: number;
  icu_total: number;
  icu_available: number;
  emergency_total: number;
  emergency_available: number;
  ventilators_total: number;
  ventilators_available: number;
}

// --- Bed Grid & Concurrency System ---
export type BedStatus = "available" | "occupied" | "reserved" | "maintenance";

export interface BedStatusResponse {
  id: number;
  bed_number: string;
  bed_type: string;
  status: BedStatus;
  has_monitor: boolean;
  has_oxygen: boolean;
  ward_id: number;
  ward_name: string;
  ward_type: string;
  reservation_expires_at: string | null;
}

export interface WardBedGrid {
  ward_id: number;
  ward_name: string;
  ward_type: string;
  floor: number | null;
  total_beds: number;
  available_beds: number;
  beds: BedStatusResponse[];
}

export interface BedGridResponse {
  hospital_id: number;
  wards: WardBedGrid[];
  total_beds: number;
  total_available: number;
  total_occupied: number;
  total_reserved: number;
  total_maintenance: number;
  generated_at: string;
}

export interface BedReserveRequest {
  bed_id: number;
  hospital_id: number;
  patient_name: string;
  triage_score: number; // 1 (Critical) to 5 (Non-urgent)
}

export interface BedReserveResponse {
  success: boolean;
  reservation_token: string;
  bed_id: number;
  bed_number: string;
  ward_name: string;
  ward_type: string;
  bed_type: string;
  status: "reserved";
  expires_at: string;
  ttl_seconds: number;
  message: string;
}

export interface BedConflictResponse {
  error: "bed_unavailable";
  message: string;
  bed_status: BedStatus;
  ward_name: string;
  queue_position: number;
  alternative_beds: Array<{
    bed_id: number;
    bed_number: string;
    bed_type: string;
    ward_name: string;
  }>;
}

// --- Predictions & Allocation ---
export interface PredictionItem {
  id: number;
  hospital_id: number;
  prediction_time: string;
  predicted_total_admissions: number;
  predicted_icu_admissions: number;
  predicted_emergency_admissions: number;
  confidence_score: number;
  surge_level: "low" | "moderate" | "high" | "critical";
}

export interface AllocationPlan {
  hospital_id: number;
  generated_at: string;
  overall_risk_level: string;
  recommendations: Array<{
    resource_type: string;
    action: string;
    quantity: number;
    urgency: string;
    rationale: string;
  }>;
}

// --- Ambulances & Telemetry ---
export interface Ambulance {
  id: number;
  vehicle_number: string;
  status: "available" | "dispatched" | "en_route" | "in_transit" | "maintenance";
  current_latitude: number;
  current_longitude: number;
  destination_hospital_id: number | null;
  patient_triage_score: number | null;
  eta_minutes: number | null;
  has_oxygen: boolean;
  has_ventilator: boolean;
}

// --- Alerts ---
export interface Alert {
  id: number;
  hospital_id: number;
  alert_type: string;
  severity: "info" | "warning" | "critical";
  message: string;
  is_acknowledged: boolean;
  created_at: string;
}
```

---

## 4. UI Architecture & Suggested Views for Stitch

### Screen 1: Command Center Overview
- **Hospital Header**: Dropdown to switch hospital (`1: City General Hospital`, `2: Metro Emergency Center`, `3: District Public Hospital`).
- **Telemetry Bar**: Live occupancy percentage, ICU availability bar, active ambulance count, ambient weather & surge risk factor.
- **Surge Prediction Chart**: Area chart comparing current vs. predicted demand across next 4, 12, and 24 hours.
- **Alert Drawer**: Pulsing badge showing unacknowledged critical alerts.

### Screen 2: Interactive Bed Matrix (Concurrency Safety Showcase)
- **Ward Selectors**: Filter by ICU, Emergency, General Medical, Surgical.
- **Live Tile Grid**:
  - Available (Green)
  - Reserved (Amber with countdown timer)
  - Occupied (Red)
  - Maintenance (Gray)
- **"Book Now" Flow**:
  1. User selects an available bed.
  2. Dialog prompts for Patient Name & Triage Urgency (1–5).
  3. Clicking "Confirm Hold" hits `POST /api/v1/beds/reserve`.
  4. On Success: Displays 5-minute countdown clock and token with "Finalize Admission" (`/confirm`) and "Release Bed" (`/release`) actions.
  5. On 409 Conflict: Displays a clean conflict banner ("Bed was secured milliseconds ago by another coordinator") + indicates waiting queue position + shows 3 clickable alternative beds with instant 1-click hold.

### Screen 3: AI Surge Simulator & Optimizer
- Interactive sliders for:
  - Temperature anomaly (simulates heatwaves / cold snaps)
  - Mass gathering attendance (e.g. concert, marathon, festival)
- "Run Surge Forecast" button calling `POST /api/v1/predictions/generate`.
- Allocation Engine output displaying mathematical resource adjustments (linear programming results).

### Screen 4: Ambulance Telemetry Radar
- List of ambulances with live status pill, ETA countdown, patient urgency badge, and vehicle capabilities (ventilator, oxygen).

---

## 5. WebSocket Integration Guide

To subscribe to real-time alerts in JavaScript/TypeScript:

```javascript
const hospitalId = 1; // Or null for all hospitals
const wsUrl = hospitalId 
  ? `ws://localhost:8000/ws/alerts/${hospitalId}` 
  : `ws://localhost:8000/ws/alerts`;

const socket = new WebSocket(wsUrl);

socket.onopen = () => {
  console.log("Connected to Real-Time Alert Broadcast");
  // Optional heartbeat ping every 30s
  setInterval(() => {
    if (socket.readyState === WebSocket.OPEN) {
      socket.send("ping");
    }
  }, 30000);
};

socket.onmessage = (event) => {
  if (event.data === "pong") return;
  const alert = JSON.parse(event.data);
  console.log("New Alert Received:", alert);
  // Trigger toast or update alert badge
};

socket.onclose = () => {
  console.log("Alert stream closed. Reconnecting...");
  setTimeout(initWebSocket, 3000);
};
```
