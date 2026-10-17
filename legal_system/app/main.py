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
from fastapi.responses import JSONResponse

from legal_system.app.config import settings
from legal_system.app.database import init_db
from legal_system.app.seed import seed_legal_data
from legal_system.app.routers import auth, cases, evidence, audit

logger = logging.getLogger("legal_vault")


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


@app.get("/", include_in_schema=False)
def root():
    """Root entrypoint returning API metadata."""
    return JSONResponse(
        {
            "service": settings.PROJECT_NAME,
            "version": "1.0.0",
            "status": "online",
            "api_docs": "/docs",
            "redoc": "/redoc",
            "endpoints": {
                "auth": "/api/v1/auth",
                "cases": "/api/v1/cases",
                "evidence": "/api/v1/evidence",
                "audit": "/api/v1/audit",
            },
        }
    )
