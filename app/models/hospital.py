"""Hospital, Ward, and Bed ORM models."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Hospital(Base):
    """Hospital entity — the top-level organizational unit."""

    __tablename__ = "hospitals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False, default="Bangalore")
    state: Mapped[str] = mapped_column(String(100), nullable=False, default="Karnataka")
    latitude: Mapped[float] = mapped_column(Float, nullable=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=True)

    total_beds: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    icu_beds: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    emergency_beds: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    ventilator_beds: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    tier: Mapped[str] = mapped_column(
        Enum("primary", "secondary", "tertiary", name="hospital_tier"),
        nullable=False,
        default="secondary",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    wards: Mapped[list["Ward"]] = relationship("Ward", back_populates="hospital", cascade="all, delete-orphan")
    staff: Mapped[list["Staff"]] = relationship("Staff", back_populates="hospital", cascade="all, delete-orphan")
    ambulances: Mapped[list["Ambulance"]] = relationship("Ambulance", back_populates="hospital", cascade="all, delete-orphan")
    admissions: Mapped[list["Admission"]] = relationship("Admission", back_populates="hospital")
    predictions: Mapped[list["Prediction"]] = relationship("Prediction", back_populates="hospital")
    alerts: Mapped[list["Alert"]] = relationship("Alert", back_populates="hospital", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Hospital(id={self.id}, name='{self.name}', tier='{self.tier}')>"


class Ward(Base):
    """Ward within a hospital — groups beds by department/type."""

    __tablename__ = "wards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hospital_id: Mapped[int] = mapped_column(Integer, ForeignKey("hospitals.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    ward_type: Mapped[str] = mapped_column(
        Enum("general", "icu", "emergency", "maternity", "pediatric", "surgical", "isolation", name="ward_type"),
        nullable=False,
        default="general",
    )
    floor: Mapped[int] = mapped_column(Integer, nullable=True)
    total_beds: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    available_beds: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    hospital: Mapped["Hospital"] = relationship("Hospital", back_populates="wards")
    beds: Mapped[list["Bed"]] = relationship("Bed", back_populates="ward", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Ward(id={self.id}, name='{self.name}', type='{self.ward_type}')>"


class Bed(Base):
    """Individual bed within a ward."""

    __tablename__ = "beds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ward_id: Mapped[int] = mapped_column(Integer, ForeignKey("wards.id"), nullable=False)
    bed_number: Mapped[str] = mapped_column(String(20), nullable=False)
    bed_type: Mapped[str] = mapped_column(
        Enum("general", "icu", "ventilator", "isolation", "maternity", name="bed_type"),
        nullable=False,
        default="general",
    )
    status: Mapped[str] = mapped_column(
        Enum("available", "occupied", "reserved", "maintenance", name="bed_status"),
        nullable=False,
        default="available",
    )
    has_monitor: Mapped[bool] = mapped_column(Boolean, default=False)
    has_oxygen: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    ward: Mapped["Ward"] = relationship("Ward", back_populates="beds")
    admissions: Mapped[list["Admission"]] = relationship("Admission", back_populates="bed")

    def __repr__(self) -> str:
        return f"<Bed(id={self.id}, number='{self.bed_number}', status='{self.status}')>"


# Avoid circular imports — these are string-referenced in relationships
from app.models.staff import Staff  # noqa: E402, F811
from app.models.ambulance import Ambulance  # noqa: E402, F811
from app.models.patient import Admission  # noqa: E402, F811
from app.models.prediction import Prediction  # noqa: E402, F811
from app.models.alert import Alert  # noqa: E402, F811
