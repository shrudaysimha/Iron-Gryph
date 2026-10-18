"""
FastAPI application entry point.

This file creates the FastAPI app, configures CORS (so the frontend dashboard
can call the API from a different port/domain), and mounts all routes.

TO RUN:
    uvicorn app.main:app --reload --port 8000

Then open http://localhost:8000/docs for the interactive Swagger UI.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routes import router

# ═══════════════════════════════════════════════════════════════════════
#  APP CREATION
# ═══════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Log configuration on startup for debugging."""
    print("=" * 60)
    print("  Incident Detection Engine — Starting Up")
    print("=" * 60)
    print(f"  Hospital : {settings.hospital_name}")
    print(f"  Location : ({settings.hospital_latitude}, {settings.hospital_longitude})")
    print(f"  Nearby   : {settings.nearby_radius_km} km radius")
    print(f"  Weather  : {'API configured' if settings.weather_api_key else 'Simulated mode'}")
    print(f"  Events   : {'API configured' if settings.events_api_key else 'Simulated mode'}")
    print(f"  Docs     : http://localhost:{settings.api_port}/docs")
    print("=" * 60)
    yield


app = FastAPI(
    title="Incident Detection Engine — Hospital Patient Surge Prediction",
    description=(
        "External Intelligence & Incident Detection module (Member 4).\n\n"
        "Detects external events (accidents, weather, public gatherings) that "
        "may cause an increase in hospital emergency patients.\n\n"
        "**DISCLAIMER:** All sample data is SIMULATED. Risk scores are "
        "illustrative heuristics, NOT clinically validated predictions."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ═══════════════════════════════════════════════════════════════════════
#  CORS MIDDLEWARE
# ═══════════════════════════════════════════════════════════════════════
# This allows the frontend dashboard (running on a different port, e.g.
# localhost:3000) to call these APIs without browser CORS errors.

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════
#  MOUNT ROUTES
# ═══════════════════════════════════════════════════════════════════════

app.include_router(router)



