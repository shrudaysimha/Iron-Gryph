"""Audit Logging Service — Writes immutable audit ledger records for chain of custody."""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from legal_system.app.models import AuditLog, User


def log_audit_event(
    db: Session,
    action: str,
    resource_type: str,
    details: str,
    user: Optional[User] = None,
    resource_id: Optional[str] = None,
    sha256_snapshot: Optional[str] = None,
    ip_address: str = "127.0.0.1",
) -> AuditLog:
    """Record an audit trail event in the immutable database log."""
    log_entry = AuditLog(
        timestamp=datetime.now(timezone.utc),
        user_id=user.id if user else None,
        username=user.username if user else "System/Anonymous",
        user_role=user.role if user else "system",
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        details=details,
        sha256_snapshot=sha256_snapshot,
        ip_address=ip_address,
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry
