"""Ambulance ORM model — fleet tracking and dispatch."""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Ambulance(Base):
    """Ambulance entity — vehicle in a hospital's fleet."""

    __tablename__ = "ambulances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hospital_id: Mapped[int] = mapped_column(Integer, ForeignKey("hospitals.id"), nullable=False)

    vehicle_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    vehicle_type: Mapped[str] = mapped_column(
        Enum("basic", "advanced", "icu_mobile", "neonatal", name="ambulance_type"),
        nullable=False,
        default="basic",
    )
    status: Mapped[str] = mapped_column(
        Enum("available", "dispatched", "en_route", "at_scene", "returning", "maintenance", "off_duty", name="ambulance_status"),
        nullable=False,
        default="available",
    )

    # Live tracking
    current_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    destination_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    destination_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    destination_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    eta_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Crew
    driver_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    paramedic_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    last_dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_maintenance_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    hospital: Mapped["Hospital"] = relationship("Hospital", back_populates="ambulances")

    def __repr__(self) -> str:
        return f"<Ambulance(id={self.id}, vehicle='{self.vehicle_number}', status='{self.status}')>"


# Avoid circular imports
from app.models.hospital import Hospital  # noqa: E402, F811
