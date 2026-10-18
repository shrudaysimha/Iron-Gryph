"""Resource Allocation API endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.prediction import Prediction, AllocationRecommendation
from app.schemas.allocation import (
    AllocationRecommendationResponse,
    AllocationPlan,
    ApplyAllocationRequest,
)
from app.services.allocation_service import AllocationService

router = APIRouter()


@router.get("/recommend", response_model=AllocationPlan)
def get_allocation_recommendation(
    hospital_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Get AI-powered resource allocation recommendations."""
    service = AllocationService(db)
    plan = service.generate_allocation_plan(hospital_id=hospital_id)
    return plan


from fastapi import Request


@router.post("/apply", status_code=200)
async def apply_allocation(
    request: Request,
    hospital_id: int = Query(default=1),
    db: Session = Depends(get_db),
):
    """Apply recommended resource allocations."""
    # Attempt to parse json body if provided
    prediction_id = None
    rec_ids = None
    try:
        body = await request.json()
        if isinstance(body, dict):
            prediction_id = body.get("prediction_id")
            rec_ids = body.get("recommendation_ids")
    except Exception:
        pass

    if not prediction_id:
        # Fallback to latest prediction for this hospital
        latest_pred = (
            db.query(Prediction)
            .filter(Prediction.hospital_id == hospital_id)
            .order_by(Prediction.created_at.desc())
            .first()
        )
        if not latest_pred:
            raise HTTPException(status_code=404, detail="No active prediction found for hospital")
        prediction_id = latest_pred.id

    prediction = db.query(Prediction).filter(Prediction.id == prediction_id).first()
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")

    recommendations_query = db.query(AllocationRecommendation).filter(
        AllocationRecommendation.prediction_id == prediction_id
    )

    if rec_ids:
        recommendations_query = recommendations_query.filter(
            AllocationRecommendation.id.in_(rec_ids)
        )

    recommendations = recommendations_query.all()
    if not recommendations:
        # If no unapplied recommendations, check if any exist at all
        all_recs = db.query(AllocationRecommendation).filter(
            AllocationRecommendation.prediction_id == prediction_id
        ).all()
        if not all_recs:
            raise HTTPException(status_code=404, detail="No recommendations found")
        recommendations = all_recs

    now = datetime.now(timezone.utc)
    for rec in recommendations:
        rec.applied = True
        rec.applied_at = now

    db.commit()

    # Broadcast via WebSocket
    try:
        from app.main import alert_manager
        await alert_manager.broadcast_alert({
            "type": "ALLOCATIONS_APPLIED",
            "message": f"Applied {len(recommendations)} allocation recommendations across beds, staff, and EMS",
            "data": {
                "hospital_id": hospital_id,
                "applied_count": len(recommendations),
                "prediction_id": prediction_id,
                "timestamp": now.isoformat(),
            }
        }, hospital_id=hospital_id)
    except Exception:
        pass

    return {
        "message": f"Applied {len(recommendations)} allocation recommendations",
        "applied_count": len(recommendations),
        "prediction_id": prediction_id,
    }

