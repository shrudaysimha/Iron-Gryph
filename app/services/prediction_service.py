"""Prediction service — orchestrates ML model to generate demand forecasts."""

from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.models.hospital import Hospital, Ward
from app.models.patient import Admission
from app.models.ambulance import Ambulance
from app.models.prediction import Prediction
from app.ml.demand_model import DemandModel
from app.ml.feature_engineering import FeatureEngineer


class PredictionService:
    """Service layer for demand predictions."""

    def __init__(self, db: Session):
        self.db = db
        self.feature_engineer = FeatureEngineer(db)
        self.model = DemandModel()

    def generate_predictions(
        self,
        hospital_id: int,
        horizon_hours: int = 4,
    ) -> list[Prediction]:
        """Generate demand predictions for multiple horizons."""
        hospital = self.db.query(Hospital).filter(Hospital.id == hospital_id).first()
        if not hospital:
            raise ValueError(f"Hospital {hospital_id} not found")

        now = datetime.now(timezone.utc)
        horizons = [4, 12, 24] if horizon_hours == 4 else [horizon_hours]

        predictions = []
        for horizon in horizons:
            # Extract features
            features = self.feature_engineer.extract_features(
                hospital_id=hospital_id,
                target_time=now + timedelta(hours=horizon),
            )

            # Run prediction
            result = self.model.predict(features)

            # Determine if surge is predicted
            # Surge = predicted admissions > 1.5x average for this time of day
            avg_admissions = self._get_average_admissions(hospital_id, horizon)
            is_surge = result["total_admissions"] > avg_admissions * 1.5

            prediction = Prediction(
                hospital_id=hospital_id,
                predicted_for=now + timedelta(hours=horizon),
                horizon_hours=horizon,
                predicted_total_admissions=result["total_admissions"],
                predicted_emergency_admissions=result["emergency_admissions"],
                predicted_icu_demand=result["icu_demand"],
                predicted_surgical_demand=result["surgical_demand"],
                confidence_score=result["confidence"],
                model_version=self.model.version,
                features_used=features,
                is_surge_predicted=is_surge,
            )
            self.db.add(prediction)
            predictions.append(prediction)

        self.db.commit()
        for pred in predictions:
            self.db.refresh(pred)

        return predictions

    def _get_average_admissions(self, hospital_id: int, horizon_hours: int) -> float:
        """Get the average admissions count for similar time windows over the past 30 days."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=30)

        admissions = (
            self.db.query(Admission)
            .filter(
                Admission.hospital_id == hospital_id,
                Admission.admitted_at >= cutoff,
            )
            .count()
        )

        # Average per horizon window
        windows = 30 * 24 / horizon_hours  # Number of windows in 30 days
        return admissions / windows if windows > 0 else 5  # Default to 5 if no data
