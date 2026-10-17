"""Alert API endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.alert import Alert
from app.schemas.alert import AlertResponse, AcknowledgeAlertRequest

router = APIRouter()


@router.get("/", response_model=list[AlertResponse])
def get_alerts(
    hospital_id: int = Query(...),
    severity: str | None = None,
    unacknowledged_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Get active alerts for a hospital."""
    query = db.query(Alert).filter(
        Alert.hospital_id == hospital_id,
        Alert.resolved == False,  # noqa: E712
    )
    if severity:
        query = query.filter(Alert.severity == severity)
    if unacknowledged_only:
        query = query.filter(Alert.acknowledged == False)  # noqa: E712

    return query.order_by(Alert.created_at.desc()).limit(limit).all()


@router.put("/{alert_id}/acknowledge", response_model=AlertResponse)
def acknowledge_alert(
    alert_id: int,
    request: AcknowledgeAlertRequest,
    db: Session = Depends(get_db),
):
    """Acknowledge an alert."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.acknowledged = True
    alert.acknowledged_by = request.acknowledged_by
    alert.acknowledged_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(alert)
    return alert


@router.put("/{alert_id}/resolve", response_model=AlertResponse)
def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    """Mark an alert as resolved."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.resolved = True
    alert.resolved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(alert)
    return alert


@router.post("/evaluate", response_model=list[AlertResponse])
def evaluate_alerts(
    hospital_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Evaluate real-time metrics against safety thresholds and generate alerts."""
    from app.services.alert_service import AlertService
    service = AlertService(db)
    new_alerts = service.evaluate_and_generate_alerts(hospital_id)
    return new_alerts

