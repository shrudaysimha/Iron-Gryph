# Antigravity Frontend Implementation Specification
## Project: MediBook (Hospital Surge AI & Clinical Operations)
**Target Framework:** React (Vite / Next.js) or Flutter / React Native
**Styling Engine:** Tailwind CSS
**Design System Reference:** Light Clinical Medical Theme (Slate-50 / Sky-600 / Red-500 / Amber-500)

--- use the frontend which i have generated from stitch

## 1. System Architecture & Tech Stack

```
Frontend (React 18+ / TypeScript / Tailwind CSS)
 │
 ├── State Management: TanStack Query (React Query) + Zustand
 ├── Real-Time Feed: Native WebSocket client (`ws://localhost:8080/ws/alerts`)
 ├── HTTP Client: Axios with baseURL `http://localhost:8080/api/v1`
 └── Icons: Lucide React (or Heroicons)
```

### Core Design System Tokens (`tailwind.config.js`)
```javascript
module.exports = {
  theme: {
    extend: {
      colors: {
        base: '#F8FAFC',        // Ultra-Light Slate Gray background
        surface: '#FFFFFF',     // Pure White Cards & Panels
        brand: {
          50: '#F0F9FF',
          500: '#0284C7',       // Sky Medical Blue
          600: '#0369A1',
          700: '#075985',
        },
        surge: {
          warning: '#F97316',   // Amber Orange
          critical: '#EF4444',  // Crisp Code Red
          optimal: '#10B981',   // Emerald Green
        },
        slate: {
          900: '#0F172A',       // Primary high-contrast typography
        }
      },
      boxShadow: {
        'card': '0 1px 3px 0 rgb(0 0 0 / 0.05), 0 1px 2px -1px rgb(0 0 0 / 0.05)',
        'elevated': '0 10px 15px -3px rgb(15 23 42 / 0.05)',
      }
    }
  }
}
```

---

## 2. Global State & Real-Time Sync Architecture

### WebSocket Hook (`useAlertsWebSocket.ts`)
Connects to FastAPI `/ws/alerts` for instantaneous broadcast of surges and bed lock transitions:
```typescript
import { useEffect, useState } from 'react';

export interface AlertPayload {
  type: 'SURGE_WARNING' | 'BED_STATUS_CHANGED' | 'CAD_TELEMETRY' | 'CODE_RED';
  message: string;
  data: any;
  timestamp: string;
}

export function useAlertsWebSocket(hospitalId: string = "sids-surat") {
  const [latestAlert, setLatestAlert] = useState<AlertPayload | null>(null);

  useEffect(() => {
    const socket = new WebSocket(`ws://localhost:8080/ws/alerts/${hospitalId}`);

    socket.onmessage = (event) => {
      try {
        const payload: AlertPayload = JSON.parse(event.data);
        setLatestAlert(payload);
      } catch (err) {
        console.error("WS Parse error", err);
      }
    };

    socket.onerror = (err) => console.error("WebSocket error:", err);
    return () => socket.close();
  }, [hospitalId]);

  return { latestAlert };
}
```

---

## 3. Screen Specifications & Route Mapping

The MediBook mobile application is structured around a persistent 4-tab mobile layout:
1. `/triage` — Emergency Triage & Intake
2. `/beds` — Live Bed Census & Pessimistic Concurrency Engine
3. `/ems` — CAD Live Ambulance Telemetry
4. `/doctors` — On-Duty Specialists, OPD Queue & E-Prescriptions

---

### Route 1: `/triage` — Emergency Triage & Intake Hub
**Primary Goal:** Fast 1-tap admission, trauma callout, and ESI (Emergency Severity Index 1–5) queue.

#### API Endpoints Used:
- `GET /api/v1/patients/live-er` — Live emergency queue & wait times
- `POST /api/v1/alerts/stat-callout` — Trigger Code Red / Mass Casualty Protocol
- `POST /api/v1/patients/{id}/fast-track` — Admit immediately to Resuscitation Bay

#### Component Hierarchy:
```
TriageScreen
 ├── GlobalHeader (SIDS Hospital Surat • LIVE indicator)
 ├── CodeRedBanner (STAT Trauma Alert button with pulsing border)
 ├── ERTelemetryGrid (Total ER: 34, Avg Wait: 12m, Resus Bays Free: 2/6, Shift MDs: 14)
 ├── ESISpectrumSelector (ESI 1: Red to ESI 5: Gray)
 ├── InboundTriageList
 │    ├── PatientTriageCard (Acuity badge, ECG/Vitals preview, ETA, "Fast-Track Admit" CTA)
 └── EmergencyResponseTools (Register Walk-In, MCI Protocol, ICU Transfer)
```

---

### Route 2: `/beds` — Live Bed Census & Concurrency Lock Engine
**Primary Goal:** Resolve the "100-User Problem" via atomic bed reservation with 5-minute TTL locks and LP surge rerouting.

#### API Endpoints Used:
- `GET /api/v1/beds` — Full hospital bed map with ward filter
- `POST /api/v1/beds/reserve` — Pessimistic lock request (`SELECT FOR UPDATE`). Payload: `{ bed_id: string, coordinator_id: string }`
  - Returns `200 OK` with `{ token: string, ttl_seconds: 300, expires_at: string }`
  - Returns `409 Conflict` with `{ error: string, queue_position: number, alternative_beds: Bed[] }`
- `POST /api/v1/beds/confirm` — Transition bed from `reserved` to `occupied`
- `POST /api/v1/beds/release` — Manual release back to `available`

#### Key UI States for Bed Card (`BedCard.tsx`):
1. **Available State:** Clean card, ventilator readiness badge, nominal O2 PSI reading, blue `Reserve Bed (5-Min Hold)` button.
2. **Locked State (Holding Coordinator):** Countdown timer (`04:34`), reservation token pill, `Confirm Admission` and `Abort Hold` actions.
3. **Contested State (409 Conflict):** "Locked by Coordinator A (#4 in queue)" with 3 instant alternatives suggested by the LP solver.

---

### Route 3: `/ems` — Live CAD Ambulance Telemetry
**Primary Goal:** Monitor incoming critical trauma vehicles, real-time vitals, and hospital diversion status.

#### API Endpoints Used:
- `GET /api/v1/ambulances/active` — Real-time coordinates, speed, ETA, and patient vitals
- `POST /api/v1/hospitals/diversion-status` — Toggle accepting vs. diverted status

#### Key Data Model:
```typescript
interface AmbulanceTelemetry {
  id: string; // e.g., "#AMB-108"
  unit_type: "ALS" | "BLS";
  eta_minutes: number;
  speed_kmh: number;
  location_corridor: string;
  patient: {
    age_gender: string;
    condition: string;
    gcs_score: string; // e.g., "9/15"
    spo2: number;
    heart_rate: number;
    bp: string;
  };
  equipment: {
    defibrillator: boolean;
    ventilator_active: boolean;
  };
}
```

---

### Route 4: `/doctors` — Doctors, OPD & E-Prescriptions
**Primary Goal:** Digital outpatient scheduling, live queue tracking, and cryptographic e-prescriptions.

#### API Endpoints Used:
- `GET /api/v1/opd/queue-status` — Live token status (`#B-24`, 5 behind, ~15m wait)
- `GET /api/v1/staff/doctors` — On-duty specialists with walk-in vs. teleconsultation availability
- `GET /api/v1/prescriptions/{patient_id}` — Verified prescription with SHA-256 integrity seal
- `POST /api/v1/pharmacy/order` — Send prescription items directly to hospital pharmacy

---

## 4. Complete Ready-to-Implement React Screen Template

```tsx
// src/screens/BedCensusScreen.tsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';

interface Bed {
  id: string;
  ward: string;
  status: 'available' | 'locked' | 'occupied' | 'sanitizing';
  ventilator: string;
  o2_psi: number;
}

export const BedCensusScreen: React.FC = () => {
  const [beds, setBeds] = useState<Bed[]>([]);
  const [holdingToken, setHoldingToken] = useState<string | null>(null);
  const [conflictNotice, setConflictNotice] = useState<any | null>(null);

  const reserveBed = async (bedId: string) => {
    try {
      setConflictNotice(null);
      const res = await axios.post('/api/v1/beds/reserve', {
        bed_id: bedId,
        coordinator_id: 'coord_alpha_99'
      });
      setHoldingToken(res.data.token);
    } catch (err: any) {
      if (err.response?.status === 409) {
        setConflictNotice(err.response.data);
      }
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 pb-20">
      {/* Telemetry Header */}
      <div className="bg-white border-b border-slate-100 p-4 sticky top-0 z-10">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">FastAPI Telemetry :8080</span>
          </div>
          <span className="text-xs bg-sky-50 text-sky-700 font-semibold px-2 py-0.5 rounded-full border border-sky-100">
            Row Lock Guard
          </span>
        </div>
      </div>

      <div className="p-4 space-y-4 max-w-md mx-auto">
        {conflictNotice && (
          <div className="p-4 bg-orange-50 border border-orange-200 rounded-2xl text-sm">
            <p className="font-bold text-orange-900">HTTP 409 Resource Conflict</p>
            <p className="text-orange-700 mt-1">{conflictNotice.error} — You are #{conflictNotice.queue_position} in line.</p>
          </div>
        )}

        {/* Sample Bed Item */}
        <div className="bg-white border border-slate-100 rounded-2xl p-4 shadow-sm">
          <div className="flex justify-between items-center mb-2">
            <h3 className="font-bold text-base">Bed #ICU-102</h3>
            <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-100">
              AVAILABLE
            </span>
          </div>
          <p className="text-xs text-slate-500 mb-4">Hamilton G5 Ready • 98 PSI O2 Nominal</p>
          <button
            onClick={() => reserveBed('ICU-102')}
            className="w-full py-2.5 bg-sky-600 hover:bg-sky-700 text-white rounded-xl font-medium text-sm transition-colors shadow-sm"
          >
            Reserve Bed (5-Min Lock)
          </button>
        </div>
      </div>
    </div>
  );
};
```

---

## 5. Antigravity Execution Instructions
When opening Antigravity or your AI agent in your IDE:
1. Place this file in your root folder as `FRONTEND_SPECIFICATION.md`.
2. Instruct the agent:
   > *"Read FRONTEND_SPECIFICATION.md. Build the 4 screens under `/src/screens` using React, TypeScript, and Tailwind CSS. Connect the API calls to `http://localhost:8080/api/v1` and WebSocket to `ws://localhost:8080/ws/alerts`."*
