"""Staff ORM model — doctors, nurses, paramedics."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Staff(Base):
    """Staff member — doctor, nurse, or paramedic at a hospital."""

    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hospital_id: Mapped[int] = mapped_column(Integer, ForeignKey("hospitals.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(
        Enum("doctor", "nurse", "paramedic", "surgeon", "specialist", "admin", name="staff_role"),
        nullable=False,
    )
    specialization: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Shift management
    current_shift: Mapped[str] = mapped_column(
        Enum("morning", "afternoon", "night", "off", name="shift_type"),
        nullable=False,
        default="off",
    )
    on_duty: Mapped[bool] = mapped_column(Boolean, default=False)
    shift_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    shift_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Availability
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    max_patients: Mapped[int] = mapped_column(Integer, default=10, comment="Max concurrent patients")
    current_patients: Mapped[int] = mapped_column(Integer, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    hospital: Mapped["Hospital"] = relationship("Hospital", back_populates="staff")
    admissions: Mapped[list["Admission"]] = relationship("Admission", back_populates="attending_doctor")

    def __repr__(self) -> str:
        return f"<Staff(id={self.id}, name='{self.name}', role='{self.role}')>"


# Avoid circular imports
from app.models.hospital import Hospital  # noqa: E402, F811
from app.models.patient import Admission  # noqa: E402, F811
