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


@router.post("/stat-callout")
async def trigger_stat_callout(
    hospital_id: int = Query(default=1),
    message: str = Query(default="STAT Trauma Alert: Mass Casualty Inbound"),
    db: Session = Depends(get_db),
):
    """Trigger Code Red / Mass Casualty Protocol and broadcast to all connected WebSocket clients."""
    from app.models.alert import Alert
    alert = Alert(
        hospital_id=hospital_id,
        alert_type="mass_casualty",
        severity="critical",
        title="CODE RED: STAT TRAUMA CALLOUT",
        message=message,
        acknowledged=False,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    # Broadcast via WebSocket
    try:
        from app.main import alert_manager
        await alert_manager.broadcast_alert({
            "type": "CODE_RED",
            "message": alert.message,
            "data": {
                "alert_id": alert.id,
                "hospital_id": hospital_id,
                "severity": "critical",
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, hospital_id=hospital_id)
    except Exception:
        pass

    return {
        "success": True,
        "alert_id": alert.id,
        "type": "CODE_RED",
        "message": alert.message,
        "protocol": "Mass Casualty Protocol Activated",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


