"""Pydantic schemas for Resource Allocation."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AllocationRecommendationResponse(BaseModel):
    id: int
    prediction_id: int
    resource_type: str
    current_available: int
    recommended_available: int
    action: str
    priority: str
    reasoning: str | None
    applied: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AllocationPlan(BaseModel):
    """Full allocation plan with all resource recommendations."""
    hospital_id: int
    hospital_name: str
    prediction_id: int
    generated_at: datetime
    overall_risk_level: str  # critical, high, medium, low
    recommendations: list[AllocationRecommendationResponse]
    summary: str


class ApplyAllocationRequest(BaseModel):
    prediction_id: int
    recommendation_ids: list[int] | None = None  # None = apply all
