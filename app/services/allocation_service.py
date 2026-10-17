"""Allocation service — generates resource allocation recommendations using optimization."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.hospital import Hospital, Ward, Bed
from app.models.patient import Admission
from app.models.staff import Staff
from app.models.ambulance import Ambulance
from app.models.prediction import Prediction, AllocationRecommendation
from app.schemas.allocation import AllocationPlan, AllocationRecommendationResponse
from app.ml.optimizer import ResourceOptimizer


class AllocationService:
    """Service layer for resource allocation recommendations."""

    def __init__(self, db: Session):
        self.db = db
        self.optimizer = ResourceOptimizer()

    def generate_allocation_plan(self, hospital_id: int) -> AllocationPlan:
        """Generate a complete resource allocation plan for a hospital."""
        hospital = self.db.query(Hospital).filter(Hospital.id == hospital_id).first()
        if not hospital:
            raise ValueError(f"Hospital {hospital_id} not found")

        # Get latest prediction
        latest_prediction = (
            self.db.query(Prediction)
            .filter(Prediction.hospital_id == hospital_id)
            .order_by(Prediction.created_at.desc())
            .first()
        )

        # If no prediction exists, generate one first
        if not latest_prediction:
            from app.services.prediction_service import PredictionService
            pred_service = PredictionService(self.db)
            predictions = pred_service.generate_predictions(hospital_id)
            latest_prediction = predictions[0] if predictions else None

        if not latest_prediction:
            raise ValueError("Could not generate predictions for allocation planning")

        # Get current state
        current_state = self._get_current_state(hospital_id)

        # Run optimizer
        recommendations = self.optimizer.optimize(
            prediction=latest_prediction,
            current_state=current_state,
        )

        # Save recommendations
        db_recommendations = []
        for rec in recommendations:
            db_rec = AllocationRecommendation(
                prediction_id=latest_prediction.id,
                resource_type=rec["resource_type"],
                current_available=rec["current_available"],
                recommended_available=rec["recommended_available"],
                action=rec["action"],
                priority=rec["priority"],
                reasoning=rec["reasoning"],
            )
            self.db.add(db_rec)
            db_recommendations.append(db_rec)

        self.db.commit()
        for rec in db_recommendations:
            self.db.refresh(rec)

        # Determine overall risk level
        risk_levels = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        max_risk = max(risk_levels.get(r.priority, 0) for r in db_recommendations) if db_recommendations else 1
        risk_map = {4: "critical", 3: "high", 2: "medium", 1: "low"}
        overall_risk = risk_map.get(max_risk, "low")

        # Generate summary
        summary = self._generate_summary(db_recommendations, overall_risk, latest_prediction)

        return AllocationPlan(
            hospital_id=hospital_id,
            hospital_name=hospital.name,
            prediction_id=latest_prediction.id,
            generated_at=datetime.now(timezone.utc),
            overall_risk_level=overall_risk,
            recommendations=[
                AllocationRecommendationResponse.model_validate(r) for r in db_recommendations
            ],
            summary=summary,
        )

    def _get_current_state(self, hospital_id: int) -> dict:
        """Get the current resource state of a hospital."""
        wards = self.db.query(Ward).filter(Ward.hospital_id == hospital_id, Ward.is_active == True).all()  # noqa: E712
        total_beds = sum(w.total_beds for w in wards)
        available_beds = sum(w.available_beds for w in wards)

        icu_wards = [w for w in wards if w.ward_type == "icu"]
        icu_available = sum(w.available_beds for w in icu_wards)

        on_duty_doctors = (
            self.db.query(Staff)
            .filter(Staff.hospital_id == hospital_id, Staff.role == "doctor", Staff.on_duty == True)  # noqa: E712
            .count()
        )
        on_duty_nurses = (
            self.db.query(Staff)
            .filter(Staff.hospital_id == hospital_id, Staff.role == "nurse", Staff.on_duty == True)  # noqa: E712
            .count()
        )

        available_ambulances = (
            self.db.query(Ambulance)
            .filter(Ambulance.hospital_id == hospital_id, Ambulance.status == "available")
            .count()
        )
        total_ambulances = (
            self.db.query(Ambulance)
            .filter(Ambulance.hospital_id == hospital_id)
            .count()
        )

        ventilator_beds = (
            self.db.query(Bed)
            .join(Ward)
            .filter(Ward.hospital_id == hospital_id, Bed.bed_type == "ventilator", Bed.status == "available")
            .count()
        )

        current_patients = (
            self.db.query(Admission)
            .filter(
                Admission.hospital_id == hospital_id,
                Admission.status.in_(["admitted", "in_treatment", "observation"]),
            )
            .count()
        )

        return {
            "total_beds": total_beds,
            "available_beds": available_beds,
            "icu_available": icu_available,
            "doctors_on_duty": on_duty_doctors,
            "nurses_on_duty": on_duty_nurses,
            "available_ambulances": available_ambulances,
            "total_ambulances": total_ambulances,
            "ventilator_available": ventilator_beds,
            "current_patients": current_patients,
        }

    def _generate_summary(
        self,
        recommendations: list[AllocationRecommendation],
        risk_level: str,
        prediction: Prediction,
    ) -> str:
        """Generate a human-readable summary of the allocation plan."""
        critical = [r for r in recommendations if r.priority == "critical"]
        high = [r for r in recommendations if r.priority == "high"]

        lines = []
        if prediction.is_surge_predicted:
            lines.append(
                f"⚠️ SURGE PREDICTED: Expecting {prediction.predicted_total_admissions} "
                f"admissions in the next {prediction.horizon_hours} hours."
            )

        lines.append(f"Overall risk level: {risk_level.upper()}")

        if critical:
            lines.append(f"🔴 {len(critical)} CRITICAL actions required:")
            for r in critical:
                lines.append(f"  - {r.resource_type}: {r.reasoning}")

        if high:
            lines.append(f"🟠 {len(high)} HIGH priority recommendations:")
            for r in high:
                lines.append(f"  - {r.resource_type}: {r.reasoning}")

        increase_actions = [r for r in recommendations if r.action == "increase"]
        if increase_actions:
            lines.append(f"📈 Resources to increase: {', '.join(r.resource_type for r in increase_actions)}")

        return "\n".join(lines)
