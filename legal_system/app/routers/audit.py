"""Audit Trail Router — Immutable Chain of Custody & Forensic Security Ledger (Admin Only)."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from legal_system.app.database import get_db
from legal_system.app.models import AuditLog, User
from legal_system.app.schemas import AuditLogResponse
from legal_system.app.auth import require_admin

router = APIRouter(prefix="/audit", tags=["Audit Log & Chain of Custody (Admin Only)"])


@router.get("", response_model=List[AuditLogResponse], include_in_schema=False)
@router.get("/logs", response_model=List[AuditLogResponse], include_in_schema=False)
@router.get("/", response_model=List[AuditLogResponse])
def get_audit_trail(
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    username: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Query the immutable forensic audit ledger.
    Restricted strictly to users with the 'administrator' role.
    """
    query = db.query(AuditLog)

    if action:
        query = query.filter(AuditLog.action == action)

    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)

    if username:
        query = query.filter(AuditLog.username == username)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                AuditLog.details.ilike(search_pattern),
                AuditLog.action.ilike(search_pattern),
                AuditLog.resource_id.ilike(search_pattern),
                AuditLog.username.ilike(search_pattern),
                AuditLog.sha256_snapshot.ilike(search_pattern),
            )
        )

    logs = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()
    return logs


@router.get("/export")
def export_audit_trail(
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Export the complete audit log records for judicial presentation or compliance archive."""
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()
    return {
        "export_timestamp": str(logs[0].timestamp if logs else ""),
        "total_events": len(logs),
        "exported_by": current_admin.full_name,
        "badge_number": current_admin.badge_number,
        "events": [
            {
                "id": l.id,
                "timestamp": l.timestamp.isoformat(),
                "user": l.username,
                "role": l.user_role,
                "action": l.action,
                "resource_type": l.resource_type,
                "resource_id": l.resource_id,
                "details": l.details,
                "sha256_snapshot": l.sha256_snapshot,
                "ip_address": l.ip_address,
            }
            for l in logs
        ],
    }
