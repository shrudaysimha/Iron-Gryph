"""ORM Models package - imports all models for Alembic discovery."""

from app.models.hospital import Hospital, Ward, Bed
from app.models.patient import Patient, Admission
from app.models.staff import Staff
from app.models.ambulance import Ambulance
from app.models.resource import Resource, ResourceUsage
from app.models.alert import Alert
from app.models.prediction import Prediction, AllocationRecommendation

__all__ = [
    "Hospital",
    "Ward",
    "Bed",
    "Patient",
    "Admission",
    "Staff",
    "Ambulance",
    "Resource",
    "ResourceUsage",
    "Alert",
    "Prediction",
    "AllocationRecommendation",
]
