"""
Hospital Surge AI — Main FastAPI Application.

Predicts patient demand surges and recommends optimal resource allocation
across beds, doctors, ambulances, and emergency supplies.
"""

import time
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, List, Set

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import get_settings
from app.database import init_db, SessionLocal
from app.api.router import api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("hospital_surge_ai")

settings = get_settings()


# ---- WebSocket Connection Manager for Real-Time Alerts ----

class AlertConnectionManager:
    """Manages active WebSocket connections for real-time alert broadcasts."""

    def __init__(self):
        # hospital_id -> set of active WebSockets (None = global subscribers)
        self.active_connections: Dict[int | None, Set[WebSocket]] = {None: set()}

    async def connect(self, websocket: WebSocket, hospital_id: int | None = None):
        await websocket.accept()
        if hospital_id not in self.active_connections:
            self.active_connections[hospital_id] = set()
        self.active_connections[hospital_id].add(websocket)
        logger.info(
            f"WebSocket client connected. Hospital filter: {hospital_id}. Total active: {self.total_connections}"
        )

    def disconnect(self, websocket: WebSocket, hospital_id: int | None = None):
        if hospital_id in self.active_connections:
            self.active_connections[hospital_id].discard(websocket)
            if not self.active_connections[hospital_id] and hospital_id is not None:
                del self.active_connections[hospital_id]
        if None in self.active_connections:
            self.active_connections[None].discard(websocket)
        logger.info(f"WebSocket client disconnected. Total active: {self.total_connections}")

    async def broadcast_alert(self, alert_data: dict, hospital_id: int):
        """Broadcast an alert to subscribers of this hospital and global listeners."""
        recipients = set()
        # Hospital specific subscribers
        if hospital_id in self.active_connections:
            recipients.update(self.active_connections[hospital_id])
        # Global subscribers (listening to all hospitals)
        if None in self.active_connections:
            recipients.update(self.active_connections[None])

        disconnected = []
        for connection in recipients:
            try:
                await connection.send_json(alert_data)
            except Exception:
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn, hospital_id)

    @property
    def total_connections(self) -> int:
        return sum(len(conns) for conns in self.active_connections.values())


alert_manager = AlertConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events: startup and shutdown."""
    logger.info("Initializing Hospital Surge AI backend...")
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.warning(f"Database initialization warning: {e}")

    try:
        from legal_system.app.database import init_db as init_legal_db
        from legal_system.app.seed import seed_legal_data
        init_legal_db()
        seed_legal_data()
        logger.info("Legal & Evidence Vault DB initialized successfully.")
    except Exception as e:
        logger.warning(f"Legal database initialization warning: {e}")

    yield

    logger.info("Hospital Surge AI backend shutting down.")


# ---- FastAPI App Instance ----

app = FastAPI(
    title="Hospital Surge AI API",
    description=(
        "AI-powered hospital demand surge prediction and dynamic resource allocation engine. "
        "Integrates historical admissions, real-time arrivals, ambulance telemetry, bed capacity, "
        "and environmental variables to recommend life-saving resource adjustments."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ---- Middleware ----

# Request execution time header
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    return response


# CORS Configuration
origins = list(settings.cors_origins)
if "*" not in origins and settings.debug:
    origins.append("*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if "*" not in origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Mount Routers ----

app.include_router(api_router)

# Mount Legal System Routers under /api/v1
try:
    from legal_system.app.routers import (
        cases as legal_cases,
        evidence as legal_evidence,
        audit as legal_audit,
        auth as legal_auth,
    )
    app.include_router(legal_cases.router, prefix="/api/v1")
    app.include_router(legal_evidence.router, prefix="/api/v1")
    app.include_router(legal_audit.router, prefix="/api/v1")
    app.include_router(legal_auth.router, prefix="/api/v1/legal")
    logger.info("Mounted Legal Vault API routers successfully.")
except Exception as e:
    logger.warning(f"Could not mount Legal Vault API routers: {e}")


# ---- WebSocket Endpoints ----

@app.websocket("/ws/alerts")
async def websocket_alerts_all(websocket: WebSocket):
    """Subscribe to real-time alerts across all hospitals."""
    await alert_manager.connect(websocket, hospital_id=None)
    try:
        while True:
            # Keep connection alive; handle client pings or filters
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        alert_manager.disconnect(websocket, hospital_id=None)


@app.websocket("/ws/alerts/{hospital_id}")
async def websocket_alerts_hospital(websocket: WebSocket, hospital_id: int):
    """Subscribe to real-time alerts for a specific hospital."""
    await alert_manager.connect(websocket, hospital_id=hospital_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        alert_manager.disconnect(websocket, hospital_id=hospital_id)

# ---- Health & Root Endpoints ----

@app.get("/health", tags=["System"])
def health_check():
    """Verify application health and database connection."""
    db_status = "connected"
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception as e:
        db_status = f"unreachable: {str(e)}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "app_name": settings.app_name,
        "app_env": settings.app_env,
        "database": db_status,
        "active_websockets": alert_manager.total_connections,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# Mount static assets
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

try:
    from legal_system.app.config import settings as legal_settings
    LEGAL_UPLOADS_DIR = Path(legal_settings.upload_dir)
    LEGAL_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/legal-uploads", StaticFiles(directory=str(LEGAL_UPLOADS_DIR)), name="legal_uploads")
except Exception as e:
    logger.warning(f"Could not mount legal uploads: {e}")


@app.get("/", include_in_schema=False)
def root():
    """Serve the Iron-Gryph MedCore Command Center & Surge AI Dashboard."""
    dash_file = STATIC_DIR / "dashboard.html"
    if dash_file.exists():
        return FileResponse(str(dash_file))
    beds_file = STATIC_DIR / "beds.html"
    if beds_file.exists():
        return FileResponse(str(beds_file))
    return get_api_info()


@app.get("/dashboard", include_in_schema=False)
def serve_dashboard():
    """Serve the MedCore Surge AI Command Center Dashboard."""
    dash_file = STATIC_DIR / "dashboard.html"
    if dash_file.exists():
        return FileResponse(str(dash_file))
    return FileResponse(str(STATIC_DIR / "beds.html"))


@app.get("/command-center", include_in_schema=False)
def serve_command_center():
    """Alias for Command Center dashboard."""
    return serve_dashboard()


@app.get("/legal-vault", include_in_schema=False)
def serve_legal_vault():
    """Serve the Iron-Gryph Legal & Evidence Vault interface."""
    vault_file = STATIC_DIR / "legal-vault.html"
    if vault_file.exists():
        return FileResponse(str(vault_file))
    return JSONResponse({"status": "error", "message": "Legal Vault UI not found"})


@app.get("/login", include_in_schema=False)
def serve_login():
    """Serve the Authentication & Sign-in screen."""
    login_file = STATIC_DIR / "login.html"
    if login_file.exists():
        return FileResponse(str(login_file))
    return FileResponse(str(STATIC_DIR / "beds.html"))


@app.get("/beds", include_in_schema=False)
def serve_beds():
    """Serve the Live Bed Hub & Capacity screen."""
    beds_file = STATIC_DIR / "beds.html"
    if beds_file.exists():
        return FileResponse(str(beds_file))
    return get_api_info()


@app.get("/triage", include_in_schema=False)
def serve_triage():
    """Serve the Live Inbound Triage screen."""
    triage_file = STATIC_DIR / "triage.html"
    if triage_file.exists():
        return FileResponse(str(triage_file))
    return FileResponse(str(STATIC_DIR / "beds.html"))


@app.get("/ems-live", include_in_schema=False)
def serve_ems():
    """Serve the CAD Live Telemetry & EMS Operations screen."""
    ems_file = STATIC_DIR / "ems.html"
    if ems_file.exists():
        return FileResponse(str(ems_file))
    return FileResponse(str(STATIC_DIR / "beds.html"))


@app.get("/doctors-rx", include_in_schema=False)
def serve_doctors():
    """Serve the On-Duty Doctors & Rx screen."""
    doc_file = STATIC_DIR / "doctors.html"
    if doc_file.exists():
        return FileResponse(str(doc_file))
    return FileResponse(str(STATIC_DIR / "beds.html"))


@app.get("/api/info", tags=["System"])
def get_api_info():
    """Root info endpoint detailing all active API routes and documentation."""
    return {
        "message": "Hospital Surge AI API is running",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi": "/openapi.json",
        "endpoints": {
            "dashboard": "/api/v1/dashboard/overview?hospital_id=1",
            "hospitals": "/api/v1/hospitals/",
            "hospital_capacity": "/api/v1/hospitals/1/capacity",
            "beds_grid": "/api/v1/beds/grid?hospital_id=1",
            "beds_reserve": "/api/v1/beds/reserve",
            "beds_voice_reserve": "/api/v1/beds/voice-reserve",
            "beds_confirm": "/api/v1/beds/confirm",
            "beds_release": "/api/v1/beds/release",
            "patients": "/api/v1/patients/current?hospital_id=1",
            "staff": "/api/v1/staff/on-duty?hospital_id=1",
            "ambulances": "/api/v1/ambulances/?hospital_id=1",
            "predictions_generate": "/api/v1/predictions/generate",
            "predictions_demand": "/api/v1/predictions/demand?hospital_id=1",
            "predictions_surge_telemetry": "/api/v1/predictions/surge",
            "predictions_surge_live": "/api/v1/predictions/surge/live?hospital_id=1",
            "predictions_surge_info": "/api/v1/predictions/surge/model-info",
            "predict_surge_root": "/predict/surge",
            "allocations": "/api/v1/allocations/recommend?hospital_id=1",
            "alerts": "/api/v1/alerts/?hospital_id=1",
            "environment_weather": "/api/v1/environment/weather",
            "environment_events": "/api/v1/environment/events?hospital_id=1",
            "ws_alerts": "/ws/alerts",
            "ws_alerts_hospital": "/ws/alerts/{hospital_id}",
            "incidents_analyze": "/api/v1/incidents/analyze",
            "incidents_list": "/api/v1/incidents/",
            "incidents_alerts_latest": "/api/v1/incidents/alerts/latest",
            "incidents_weather": "/api/v1/incidents/weather",
            "incidents_events": "/api/v1/incidents/events",
            "incidents_dashboard": "/api/v1/incidents/dashboard",
            "incidents_forecast_feed": "/api/v1/incidents/forecast-feed",
            "incidents_config": "/api/v1/incidents/config",
            "incidents_health": "/api/v1/incidents/health",
        },
    }


# ---- Root /predict/surge for Member 3 Integration Contract ----
from fastapi import HTTPException
from app.schemas.prediction import WeatherSurgeRequest, WeatherSurgeResponse
from app.ml.surge_predictor import WeatherSurgePredictor

_root_surge_predictor = WeatherSurgePredictor()


@app.post("/predict/surge", response_model=WeatherSurgeResponse, tags=["Weather Surge Predictor"])
def predict_surge_root(request: WeatherSurgeRequest):
    """
    Direct root endpoint for Member 3's weather-aware hospital surge prediction.
    Enables external and microservice callers to POST directly to /predict/surge.
    """
    try:
        return _root_surge_predictor.predict_raw(
            timestamp=request.timestamp,
            arrivals_now=request.arrivals_now,
            arrivals_1h_ago=request.arrivals_1h_ago,
            arrivals_2h_ago=request.arrivals_2h_ago,
            arrivals_24h_ago=request.arrivals_24h_ago,
            arrivals_168h_ago=request.arrivals_168h_ago,
            temperature_2m=request.temperature_2m,
            relative_humidity_2m=request.relative_humidity_2m,
            precipitation=request.precipitation,
            wind_speed_10m=request.wind_speed_10m,
            weather_code=request.weather_code,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/predict/surge/health", tags=["Weather Surge Predictor"])
def predict_surge_health():
    """Health status and artifact presence for the surge prediction model."""
    return {
        "status": "ok",
        "model_artifact_available": _root_surge_predictor.is_available,
        "service": "member3-hospital-surge-predictor",
    }
