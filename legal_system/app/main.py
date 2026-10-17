"""
Legal & Investigation Document Management System — FastAPI Application.

Features:
- Role-Based Access Control (Administrator vs. Investigator)
- Case Dashboard & Metadata Organization
- Evidence Vault with Cryptographic SHA-256 Hash Verification (Green Shield / Red Warning)
- File Upload Ingress with Instant Hashing
- Immutable Audit Log & Chain of Custody Ledger (Admin Only)
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from legal_system.app.config import settings
from legal_system.app.database import init_db
from legal_system.app.seed import seed_legal_data
from legal_system.app.routers import auth, cases, evidence, audit

logger = logging.getLogger("legal_vault")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle startup: initialize DB schema and seed demo records."""
    logger.info("Initializing Legal & Investigation Evidence Vault...")
    init_db()
    seed_legal_data()
    yield
    logger.info("Legal & Investigation Evidence Vault shut down.")


app = FastAPI(
    title=settings.app_name,
    description="Enterprise Legal & Investigation Document Management System with Cryptographic SHA-256 Chain of Custody & Audit Ledger",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers under /api/v1
api_prefix = "/api/v1"
app.include_router(auth.router, prefix=api_prefix)
app.include_router(cases.router, prefix=api_prefix)
app.include_router(evidence.router, prefix=api_prefix)
app.include_router(audit.router, prefix=api_prefix)


@app.get("/health", tags=["System"])
def health_check():
    """System liveness and cryptographic module status."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "hash_algorithm": "SHA-256 (FIPS 180-4)",
        "chain_of_custody_mode": "strict_immutable",
    }


# Mount static assets for frontend
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def serve_frontend():
    """Serve the single-page application frontend."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return JSONResponse(
        {
            "message": "Legal & Investigation Document Management API is active.",
            "docs": "/docs",
        }
    )
