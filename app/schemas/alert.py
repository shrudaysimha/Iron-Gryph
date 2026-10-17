"""Pydantic schemas for Alerts."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AlertResponse(BaseModel):
    id: int
    hospital_id: int
    alert_type: str
    severity: str
    title: str
    message: str
    acknowledged: bool
    acknowledged_by: str | None
    acknowledged_at: datetime | None
    resolved: bool
    resolved_at: datetime | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AcknowledgeAlertRequest(BaseModel):
    acknowledged_by: str
