"""Main API router — mounts all v1 sub-routers."""

from fastapi import APIRouter

from app.api.v1 import hospitals, patients, staff, ambulances, predictions, allocations, alerts, dashboard, environment, beds, opd, auth, incidents

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication & Staff Sessions"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(hospitals.router, prefix="/hospitals", tags=["Hospitals"])
api_router.include_router(patients.router, prefix="/patients", tags=["Patients"])
api_router.include_router(beds.router, prefix="/beds", tags=["Bed Reservation"])
api_router.include_router(staff.router, prefix="/staff", tags=["Staff"])
api_router.include_router(ambulances.router, prefix="/ambulances", tags=["Ambulances"])
api_router.include_router(predictions.router, prefix="/predictions", tags=["Predictions"])
api_router.include_router(allocations.router, prefix="/allocations", tags=["Allocations"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["Alerts"])
api_router.include_router(environment.router, prefix="/environment", tags=["Environment & Events"])
api_router.include_router(opd.router, prefix="/opd", tags=["OPD & Prescriptions"])
api_router.include_router(incidents.router, prefix="/incidents", tags=["Incident Detection Engine"])


