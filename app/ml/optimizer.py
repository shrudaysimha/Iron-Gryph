"""Resource allocation optimizer using rule-based and linear programming approaches."""

import logging

logger = logging.getLogger(__name__)


class ResourceOptimizer:
    """
    Generates resource allocation recommendations based on predictions and current state.

    Uses a rule-based approach with thresholds and ratios, with optional PuLP-based
    linear programming for more complex multi-resource optimization.
    """

    # Threshold constants
    BED_CRITICAL_THRESHOLD = 0.90   # >90% occupancy = critical
    BED_WARNING_THRESHOLD = 0.80    # >80% = warning
    ICU_CRITICAL_THRESHOLD = 0.85
    STAFF_TO_PATIENT_MIN = 0.15     # Minimum staff:patient ratio
    AMBULANCE_MIN_AVAILABLE = 2     # At least 2 ambulances must be free
    BUFFER_MULTIPLIER = 1.3         # Keep 30% buffer above predicted demand

    def optimize(self, prediction, current_state: dict) -> list[dict]:
        """
        Generate resource allocation recommendations.

        Args:
            prediction: Prediction ORM object with demand forecasts
            current_state: dict with current resource availability

        Returns:
            List of recommendation dicts
        """
        recommendations = []

        # ---- Bed Allocation ----
        recommendations.append(self._optimize_beds(prediction, current_state))

        # ---- ICU Allocation ----
        recommendations.append(self._optimize_icu(prediction, current_state))

        # ---- Doctor Allocation ----
        recommendations.append(self._optimize_doctors(prediction, current_state))

        # ---- Nurse Allocation ----
        recommendations.append(self._optimize_nurses(prediction, current_state))

        # ---- Ambulance Allocation ----
        recommendations.append(self._optimize_ambulances(prediction, current_state))

        # ---- Ventilator Allocation ----
        recommendations.append(self._optimize_ventilators(prediction, current_state))

        return [r for r in recommendations if r is not None]

    def _optimize_beds(self, prediction, state: dict) -> dict:
        """Optimize general bed allocation."""
        available = state["available_beds"]
        total = state["total_beds"]
        predicted_need = int(prediction.predicted_total_admissions * self.BUFFER_MULTIPLIER)
        occupancy = (total - available) / total if total > 0 else 1.0

        if occupancy >= self.BED_CRITICAL_THRESHOLD:
            action = "emergency_request"
            priority = "critical"
            reasoning = (
                f"Bed occupancy at {occupancy:.0%}. Only {available} beds available. "
                f"Expected {prediction.predicted_total_admissions} new admissions. "
                f"Immediate capacity expansion needed."
            )
        elif available < predicted_need:
            action = "increase"
            priority = "high"
            reasoning = (
                f"Available beds ({available}) insufficient for predicted demand "
                f"({predicted_need} with buffer). Consider discharging stable patients "
                f"or activating surge capacity."
            )
        elif occupancy >= self.BED_WARNING_THRESHOLD:
            action = "increase"
            priority = "medium"
            reasoning = (
                f"Bed occupancy at {occupancy:.0%} (warning threshold). "
                f"Monitor closely and prepare for potential increase."
            )
        else:
            action = "maintain"
            priority = "low"
            reasoning = f"Bed capacity adequate. {available} beds available, occupancy at {occupancy:.0%}."

        return {
            "resource_type": "beds",
            "current_available": available,
            "recommended_available": max(available, predicted_need),
            "action": action,
            "priority": priority,
            "reasoning": reasoning,
        }

    def _optimize_icu(self, prediction, state: dict) -> dict:
        """Optimize ICU bed allocation."""
        available = state["icu_available"]
        predicted_icu = int(prediction.predicted_icu_demand * self.BUFFER_MULTIPLIER)

        if available <= 1:
            action = "emergency_request"
            priority = "critical"
            reasoning = f"Only {available} ICU bed(s) available. Critical shortage imminent."
        elif available < predicted_icu:
            action = "increase"
            priority = "high"
            reasoning = (
                f"ICU beds ({available}) may be insufficient for predicted ICU demand "
                f"({predicted_icu} with buffer). Consider ICU-ready conversions."
            )
        else:
            action = "maintain"
            priority = "low"
            reasoning = f"ICU capacity adequate. {available} beds available."

        return {
            "resource_type": "icu_beds",
            "current_available": available,
            "recommended_available": max(available, predicted_icu),
            "action": action,
            "priority": priority,
            "reasoning": reasoning,
        }

    def _optimize_doctors(self, prediction, state: dict) -> dict:
        """Optimize doctor staffing."""
        doctors = state["doctors_on_duty"]
        patients = state["current_patients"]
        predicted = prediction.predicted_total_admissions
        future_patients = patients + predicted

        # Target: 1 doctor per 6 patients
        target_doctors = max(2, int(future_patients / 6) + 1)

        if doctors < target_doctors * 0.6:
            action = "emergency_request"
            priority = "critical"
            reasoning = (
                f"Only {doctors} doctors on duty for {patients} current + "
                f"{predicted} predicted patients. Need at least {target_doctors}."
            )
        elif doctors < target_doctors:
            action = "increase"
            priority = "high"
            reasoning = (
                f"{doctors} doctors on duty, recommend {target_doctors} for "
                f"projected patient load of {future_patients}."
            )
        else:
            action = "maintain"
            priority = "low"
            reasoning = f"Doctor staffing adequate. {doctors} on duty for {patients} patients."

        return {
            "resource_type": "doctors",
            "current_available": doctors,
            "recommended_available": target_doctors,
            "action": action,
            "priority": priority,
            "reasoning": reasoning,
        }

    def _optimize_nurses(self, prediction, state: dict) -> dict:
        """Optimize nurse staffing."""
        nurses = state["nurses_on_duty"]
        patients = state["current_patients"]
        predicted = prediction.predicted_total_admissions
        future_patients = patients + predicted

        # Target: 1 nurse per 4 patients
        target_nurses = max(3, int(future_patients / 4) + 1)

        if nurses < target_nurses * 0.6:
            action = "emergency_request"
            priority = "critical"
            reasoning = (
                f"Only {nurses} nurses on duty for {patients} current + "
                f"{predicted} predicted patients. Need at least {target_nurses}."
            )
        elif nurses < target_nurses:
            action = "increase"
            priority = "medium"
            reasoning = (
                f"{nurses} nurses on duty, recommend {target_nurses} for "
                f"projected patient load of {future_patients}."
            )
        else:
            action = "maintain"
            priority = "low"
            reasoning = f"Nurse staffing adequate. {nurses} on duty for {patients} patients."

        return {
            "resource_type": "nurses",
            "current_available": nurses,
            "recommended_available": target_nurses,
            "action": action,
            "priority": priority,
            "reasoning": reasoning,
        }

    def _optimize_ambulances(self, prediction, state: dict) -> dict:
        """Optimize ambulance availability."""
        available = state["available_ambulances"]
        total = state["total_ambulances"]
        predicted_emergency = prediction.predicted_emergency_admissions

        # Keep enough ambulances for predicted emergency volume
        target_available = max(self.AMBULANCE_MIN_AVAILABLE, int(predicted_emergency * 0.3))

        if available < self.AMBULANCE_MIN_AVAILABLE:
            action = "emergency_request"
            priority = "critical"
            reasoning = (
                f"Only {available} ambulance(s) available (minimum: {self.AMBULANCE_MIN_AVAILABLE}). "
                f"Recall returning units or request mutual aid."
            )
        elif available < target_available:
            action = "increase"
            priority = "high"
            reasoning = (
                f"{available} ambulances available, recommend {target_available} "
                f"for {predicted_emergency} predicted emergency arrivals."
            )
        else:
            action = "maintain"
            priority = "low"
            reasoning = f"Ambulance fleet adequate. {available}/{total} available."

        return {
            "resource_type": "ambulances",
            "current_available": available,
            "recommended_available": target_available,
            "action": action,
            "priority": priority,
            "reasoning": reasoning,
        }

    def _optimize_ventilators(self, prediction, state: dict) -> dict:
        """Optimize ventilator allocation."""
        available = state["ventilator_available"]
        predicted_icu = prediction.predicted_icu_demand

        # Rough estimate: 40% of ICU patients may need ventilators
        target = max(1, int(predicted_icu * 0.4))

        if available == 0:
            action = "emergency_request"
            priority = "critical"
            reasoning = "No ventilators available. Immediate procurement or transfer needed."
        elif available < target:
            action = "increase"
            priority = "high"
            reasoning = (
                f"{available} ventilators available, recommend {target} "
                f"based on predicted ICU demand of {predicted_icu}."
            )
        else:
            action = "maintain"
            priority = "low"
            reasoning = f"Ventilator supply adequate. {available} available."

        return {
            "resource_type": "ventilators",
            "current_available": available,
            "recommended_available": target,
            "action": action,
            "priority": priority,
            "reasoning": reasoning,
        }
