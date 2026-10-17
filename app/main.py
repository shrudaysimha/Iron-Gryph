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


# ---- Application Lifespan ----

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events: startup and shutdown."""
    logger.info("Initializing Hospital Surge AI backend...")
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.warning(f"Database initialization warning: {e}")

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


@app.get("/", include_in_schema=False)
def root():
    """Serve the MediBook application or API info."""
    beds_file = STATIC_DIR / "beds.html"
    if beds_file.exists():
        return FileResponse(str(beds_file))
    return get_api_info()


@app.get("/beds", include_in_schema=False)
def serve_beds():
    """Serve the MediBook Beds screen."""
    beds_file = STATIC_DIR / "beds.html"
    if beds_file.exists():
        return FileResponse(str(beds_file))
    return get_api_info()


@app.get("/triage", include_in_schema=False)
def serve_triage():
    """Serve the MediBook Triage screen."""
    triage_file = STATIC_DIR / "triage.html"
    if triage_file.exists():
        return FileResponse(str(triage_file))
    return FileResponse(str(STATIC_DIR / "beds.html"))


@app.get("/ems-live", include_in_schema=False)
def serve_ems():
    """Serve the MediBook EMS Live screen."""
    ems_file = STATIC_DIR / "ems.html"
    if ems_file.exists():
        return FileResponse(str(ems_file))
    return FileResponse(str(STATIC_DIR / "beds.html"))


@app.get("/doctors-rx", include_in_schema=False)
def serve_doctors():
    """Serve the MediBook Doctors & Rx screen."""
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
            "beds_confirm": "/api/v1/beds/confirm",
            "beds_release": "/api/v1/beds/release",
            "patients": "/api/v1/patients/current?hospital_id=1",
            "staff": "/api/v1/staff/on-duty?hospital_id=1",
            "ambulances": "/api/v1/ambulances/?hospital_id=1",
            "predictions_generate": "/api/v1/predictions/generate",
            "predictions_demand": "/api/v1/predictions/demand?hospital_id=1",
            "allocations": "/api/v1/allocations/recommend?hospital_id=1",
            "alerts": "/api/v1/alerts/?hospital_id=1",
            "environment_weather": "/api/v1/environment/weather",
            "environment_events": "/api/v1/environment/events?hospital_id=1",
            "ws_alerts": "/ws/alerts",
            "ws_alerts_hospital": "/ws/alerts/{hospital_id}",
        },
    }
