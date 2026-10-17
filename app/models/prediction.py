"""Prediction and AllocationRecommendation ORM models."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Prediction(Base):
    """Demand prediction record — stores ML model output for a time horizon."""

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hospital_id: Mapped[int] = mapped_column(Integer, ForeignKey("hospitals.id"), nullable=False)

    # Prediction window
    predicted_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    horizon_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=4)

    # Predicted values
    predicted_total_admissions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    predicted_emergency_admissions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    predicted_icu_demand: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    predicted_surgical_demand: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Model confidence
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    model_version: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Features snapshot (JSON)
    features_used: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Actual values (filled later for model evaluation)
    actual_total_admissions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_emergency_admissions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_icu_demand: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_surge_predicted: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    hospital: Mapped["Hospital"] = relationship("Hospital", back_populates="predictions")
    recommendations: Mapped[list["AllocationRecommendation"]] = relationship(
        "AllocationRecommendation", back_populates="prediction"
    )

    def __repr__(self) -> str:
        return (
            f"<Prediction(id={self.id}, hospital={self.hospital_id}, "
            f"total={self.predicted_total_admissions}, confidence={self.confidence_score:.2f})>"
        )


class AllocationRecommendation(Base):
    """AI-generated resource allocation recommendation linked to a prediction."""

    __tablename__ = "allocation_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prediction_id: Mapped[int] = mapped_column(Integer, ForeignKey("predictions.id"), nullable=False)

    resource_type: Mapped[str] = mapped_column(
        Enum("beds", "icu_beds", "doctors", "nurses", "ambulances", "ventilators", "oxygen", name="resource_alloc_type"),
        nullable=False,
    )
    current_available: Mapped[int] = mapped_column(Integer, nullable=False)
    recommended_available: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(
        Enum("increase", "maintain", "decrease", "reallocate", "emergency_request", name="alloc_action"),
        nullable=False,
        default="maintain",
    )
    priority: Mapped[str] = mapped_column(
        Enum("critical", "high", "medium", "low", name="alloc_priority"),
        nullable=False,
        default="medium",
    )
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    applied: Mapped[bool] = mapped_column(Boolean, default=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    prediction: Mapped["Prediction"] = relationship("Prediction", back_populates="recommendations")

    def __repr__(self) -> str:
        return (
            f"<AllocationRecommendation(id={self.id}, resource='{self.resource_type}', "
            f"action='{self.action}')>"
        )


# Avoid circular imports
from app.models.hospital import Hospital  # noqa: E402, F811
