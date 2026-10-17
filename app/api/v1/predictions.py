"""Prediction API endpoints — demand forecasting."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.prediction import Prediction
from app.schemas.prediction import (
    PredictionRequest,
    PredictionResponse,
    PredictionHistory,
)
from app.services.prediction_service import PredictionService

router = APIRouter()


@router.get("/demand", response_model=list[PredictionResponse])
def get_demand_forecast(
    hospital_id: int = Query(...),
    horizon_hours: int = Query(default=4, ge=1, le=72),
    db: Session = Depends(get_db),
):
    """Get the latest demand prediction for a hospital."""
    predictions = (
        db.query(Prediction)
        .filter(
            Prediction.hospital_id == hospital_id,
            Prediction.horizon_hours == horizon_hours,
            Prediction.predicted_for >= datetime.now(timezone.utc),
        )
        .order_by(Prediction.created_at.desc())
        .limit(5)
        .all()
    )
    return predictions


@router.post("/generate", response_model=list[PredictionResponse], status_code=201)
def generate_prediction(
    request: PredictionRequest,
    db: Session = Depends(get_db),
):
    """Trigger a new demand prediction using the ML model."""
    service = PredictionService(db)
    predictions = service.generate_predictions(
        hospital_id=request.hospital_id,
        horizon_hours=request.horizon_hours,
    )
    return predictions


@router.get("/history", response_model=list[PredictionHistory])
def get_prediction_history(
    hospital_id: int = Query(...),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Get past predictions with actual values for model evaluation."""
    predictions = (
        db.query(Prediction)
        .filter(Prediction.hospital_id == hospital_id)
        .order_by(Prediction.created_at.desc())
        .limit(limit)
        .all()
    )

    results = []
    for pred in predictions:
        accuracy = None
        if pred.actual_total_admissions is not None and pred.predicted_total_admissions > 0:
            error = abs(pred.actual_total_admissions - pred.predicted_total_admissions)
            accuracy = max(0, 1 - error / pred.predicted_total_admissions)
            accuracy = round(accuracy * 100, 1)

        results.append(
            PredictionHistory(
                id=pred.id,
                hospital_id=pred.hospital_id,
                predicted_for=pred.predicted_for,
                predicted_total_admissions=pred.predicted_total_admissions,
                actual_total_admissions=pred.actual_total_admissions,
                confidence_score=pred.confidence_score,
                accuracy=accuracy,
                created_at=pred.created_at,
            )
        )
    return results


@router.post("/train", status_code=200)
def retrain_model(db: Session = Depends(get_db)):
    """Trigger retraining of the demand prediction model."""
    from app.ml.train import train_demand_model
    metrics = train_demand_model(db)
    return metrics

