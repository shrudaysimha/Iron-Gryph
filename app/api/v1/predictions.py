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


# ---- Member 3 Weather-Aware Surge Predictor Endpoints ----

from fastapi import HTTPException
from app.ml.surge_predictor import WeatherSurgePredictor
from app.schemas.prediction import (
    WeatherSurgeRequest,
    WeatherSurgeResponse,
    LiveWeatherSurgeResponse,
    SurgeModelInfoResponse,
)

surge_predictor_engine = WeatherSurgePredictor()


@router.post("/surge", response_model=WeatherSurgeResponse, tags=["Weather Surge Predictor"])
def predict_surge_telemetry(request: WeatherSurgeRequest):
    """
    Predict emergency arrival surge for the next 2 hours using Member 3's
    weather-aware machine learning model.
    """
    try:
        result = surge_predictor_engine.predict_raw(
            timestamp=request.timestamp,
            arrivals_now=request.arrivals_now,
            arrivals_1h_ago=request.arrivals_1h_ago,
            arrivals_2h_ago=request.arrivals_2h_ago,
            arrivals_24h_ago=request.arrivals_24h_ago,
            arrivals_168h_ago=request.arrivals_168h_ago,
            temperature_2m=request.temperature_2m,
            relative_humidity_2m=request.relative_humidity_2m,
            precipitation=request.precipitation,
            wind_speed_10m=request.wind_speed_10m,
            weather_code=request.weather_code,
        )
        return result
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Surge prediction failed: {exc}")


@router.get("/surge/live", response_model=LiveWeatherSurgeResponse, tags=["Weather Surge Predictor"])
def predict_surge_live_hospital(
    hospital_id: int = Query(..., description="ID of hospital to evaluate"),
    db: Session = Depends(get_db),
):
    """
    Automatically extract historical admissions from the database, gather real-time
    meteorological telemetry, and generate a 2-hour surge prediction.
    """
    try:
        result = surge_predictor_engine.predict_live_hospital(hospital_id=hospital_id, db=db)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Live surge prediction failed: {exc}")


@router.get("/surge/model-info", response_model=SurgeModelInfoResponse, tags=["Weather Surge Predictor"])
def get_surge_model_info():
    """Get metadata, MAE evaluation benchmarks, and features of the surge prediction model."""
    try:
        return surge_predictor_engine.get_model_info()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---- Dynamic Surge Simulation & Reset Lifecycle Endpoints ----
from datetime import timedelta
from app.models.alert import Alert
from app.models.prediction import AllocationRecommendation


@router.post("/simulate-surge", tags=["Surge Lifecycle"])
async def simulate_surge_influx(
    hospital_id: int = Query(default=1),
    incident_name: str = Query(default="NH-48 Highway Collision Influx"),
    expected_admissions: int = Query(default=22),
    db: Session = Depends(get_db),
):
    """
    Dynamically trigger a mass-casualty surge simulation for a hospital.
    Persists prediction, critical alerts, and actionable recommendations in the database,
    and broadcasts SURGE_ACTIVATED over WebSockets to all connected stations.
    """
    now = datetime.now(timezone.utc)

    # 1. Create or update Prediction
    pred = Prediction(
        hospital_id=hospital_id,
        predicted_for=now + timedelta(hours=2),
        horizon_hours=2,
        predicted_total_admissions=expected_admissions,
        predicted_emergency_admissions=int(expected_admissions * 0.7),
        predicted_icu_demand=int(expected_admissions * 0.3),
        predicted_surgical_demand=int(expected_admissions * 0.25),
        confidence_score=0.94,
        model_version="xgb_surge_v2.1_multi_trauma",
        is_surge_predicted=True,
    )
    db.add(pred)
    db.flush()

    # 2. Add Critical Alert
    alert = Alert(
        hospital_id=hospital_id,
        alert_type="mass_casualty",
        severity="critical",
        title="SURGE ALARM: NH-48 HIGHWAY COLLISION",
        message=f"Critical mass-casualty surge influx detected. {expected_admissions} multi-trauma admissions forecasted in 2h window.",
        acknowledged=False,
        resolved=False,
    )
    db.add(alert)

    # 3. Add dynamic Allocation Recommendations
    rec1 = AllocationRecommendation(
        prediction_id=pred.id,
        resource_type="beds",
        current_available=4,
        recommended_available=10,
        action="reallocate",
        priority="critical",
        reasoning="Convert 6 Step-Down beds in Ward 3 to High-Flow O2 bays before peak admission rush.",
        applied=False,
    )
    rec2 = AllocationRecommendation(
        prediction_id=pred.id,
        resource_type="doctors",
        current_available=12,
        recommended_available=19,
        action="emergency_request",
        priority="high",
        reasoning="Alert +3 on-call trauma surgeons and 4 ICU nurses for the 2-hour surge window.",
        applied=False,
    )
    rec3 = AllocationRecommendation(
        prediction_id=pred.id,
        resource_type="ambulances",
        current_available=3,
        recommended_available=6,
        action="reallocate",
        priority="medium",
        reasoning="Divert incoming non-critical transports to secondary facility to preserve ED capacity.",
        applied=False,
    )
    db.add_all([rec1, rec2, rec3])
    db.commit()
    db.refresh(pred)

    # 4. Broadcast over WebSocket to all stations
    try:
        from app.main import alert_manager
        await alert_manager.broadcast_alert({
            "type": "SURGE_ACTIVATED",
            "message": f"🚨 {incident_name}: Surge Protocol Armed ({expected_admissions} Expected Admissions)",
            "data": {
                "hospital_id": hospital_id,
                "surge_active": True,
                "predicted_admissions": expected_admissions,
                "prediction_id": pred.id,
                "incident_name": incident_name,
                "risk_score": 86.7,
                "timestamp": now.isoformat(),
            }
        }, hospital_id=hospital_id)
    except Exception:
        pass

    return {
        "success": True,
        "surge_active": True,
        "prediction_id": pred.id,
        "predicted_admissions": expected_admissions,
        "message": f"Surge simulation active: {expected_admissions} arrivals predicted.",
    }


@router.post("/reset-surge", tags=["Surge Lifecycle"])
async def reset_surge_influx(
    hospital_id: int = Query(default=1),
    db: Session = Depends(get_db),
):
    """
    Reset hospital surge status to baseline normal conditions.
    Resolves surge alerts and broadcasts SURGE_RESET over WebSockets.
    """
    now = datetime.now(timezone.utc)

    # 1. Create baseline normal Prediction
    pred = Prediction(
        hospital_id=hospital_id,
        predicted_for=now + timedelta(hours=2),
        horizon_hours=2,
        predicted_total_admissions=12,
        predicted_emergency_admissions=6,
        predicted_icu_demand=2,
        predicted_surgical_demand=1,
        confidence_score=0.88,
        model_version="xgb_surge_v2.1_baseline",
        is_surge_predicted=False,
    )
    db.add(pred)

    # 2. Resolve active surge alerts
    active_surge_alerts = db.query(Alert).filter(
        Alert.hospital_id == hospital_id,
        Alert.alert_type.in_(["mass_casualty", "surge_predicted"]),
        Alert.resolved == False,
    ).all()
    for a in active_surge_alerts:
        a.resolved = True
        a.resolved_at = now

    db.commit()

    # 3. Broadcast over WebSocket to all stations
    try:
        from app.main import alert_manager
        await alert_manager.broadcast_alert({
            "type": "SURGE_RESET",
            "message": "Surge Protocol Deactivated. Hospital operations returned to normal baseline.",
            "data": {
                "hospital_id": hospital_id,
                "surge_active": False,
                "predicted_admissions": 12,
                "timestamp": now.isoformat(),
            }
        }, hospital_id=hospital_id)
    except Exception:
        pass

    return {
        "success": True,
        "surge_active": False,
        "predicted_admissions": 12,
        "message": "Hospital demand reset to normal baseline.",
    }


