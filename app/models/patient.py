"""Patient and Admission ORM models."""

from datetime import datetime

from sqlalchemy import (
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


class Patient(Base):
    """Patient entity — an individual seeking or receiving care."""

    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[str] = mapped_column(
        Enum("male", "female", "other", name="gender_type"),
        nullable=False,
    )
    blood_group: Mapped[str] = mapped_column(String(10), nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    emergency_contact: Mapped[str] = mapped_column(String(20), nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=True)

    # Medical info
    condition: Mapped[str] = mapped_column(Text, nullable=True)
    triage_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3,
        comment="1=Resuscitation, 2=Emergency, 3=Urgent, 4=Semi-urgent, 5=Non-urgent"
    )
    arrival_mode: Mapped[str] = mapped_column(
        Enum("ambulance", "walk_in", "transfer", "helicopter", name="arrival_mode"),
        nullable=False,
        default="walk_in",
    )

    arrival_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    admissions: Mapped[list["Admission"]] = relationship("Admission", back_populates="patient")

    def __repr__(self) -> str:
        return f"<Patient(id={self.id}, name='{self.name}', triage={self.triage_score})>"


class Admission(Base):
    """Admission record — links a patient to a hospital stay."""

    __tablename__ = "admissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patients.id"), nullable=False)
    hospital_id: Mapped[int] = mapped_column(Integer, ForeignKey("hospitals.id"), nullable=False)
    bed_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("beds.id"), nullable=True)

    department: Mapped[str] = mapped_column(
        Enum("emergency", "general", "icu", "surgery", "maternity", "pediatric", "orthopedic", "cardiology", "neurology", name="department_type"),
        nullable=False,
        default="emergency",
    )
    diagnosis: Mapped[str] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(
        Enum("critical", "severe", "moderate", "mild", name="severity_type"),
        nullable=False,
        default="moderate",
    )
    status: Mapped[str] = mapped_column(
        Enum("admitted", "in_treatment", "observation", "discharged", "transferred", "deceased", name="admission_status"),
        nullable=False,
        default="admitted",
    )
    attending_doctor_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)

    admitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    discharged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expected_discharge: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    length_of_stay_hours: Mapped[float | None] = mapped_column(Float, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    patient: Mapped["Patient"] = relationship("Patient", back_populates="admissions")
    hospital: Mapped["Hospital"] = relationship("Hospital", back_populates="admissions")
    bed: Mapped["Bed | None"] = relationship("Bed", back_populates="admissions")
    attending_doctor: Mapped["Staff | None"] = relationship("Staff", back_populates="admissions")

    def __repr__(self) -> str:
        return f"<Admission(id={self.id}, patient={self.patient_id}, status='{self.status}')>"


# Avoid circular imports
from app.models.hospital import Hospital, Bed  # noqa: E402, F811
from app.models.staff import Staff  # noqa: E402, F811
