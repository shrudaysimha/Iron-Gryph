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


@router.post("/apply", status_code=200)
def apply_allocation(
    request: ApplyAllocationRequest,
    db: Session = Depends(get_db),
):
    """Apply recommended resource allocations."""
    prediction = db.query(Prediction).filter(Prediction.id == request.prediction_id).first()
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")

    recommendations_query = db.query(AllocationRecommendation).filter(
        AllocationRecommendation.prediction_id == request.prediction_id
    )

    if request.recommendation_ids:
        recommendations_query = recommendations_query.filter(
            AllocationRecommendation.id.in_(request.recommendation_ids)
        )

    recommendations = recommendations_query.all()
    if not recommendations:
        raise HTTPException(status_code=404, detail="No recommendations found")

    now = datetime.now(timezone.utc)
    for rec in recommendations:
        rec.applied = True
        rec.applied_at = now

    db.commit()

    return {
        "message": f"Applied {len(recommendations)} allocation recommendations",
        "applied_count": len(recommendations),
        "prediction_id": request.prediction_id,
    }
