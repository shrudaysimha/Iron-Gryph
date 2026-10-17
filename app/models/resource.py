"""Resource and ResourceUsage ORM models — equipment and supply tracking."""

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


class Resource(Base):
    """Hospital resource — equipment, supplies, or consumables."""

    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hospital_id: Mapped[int] = mapped_column(Integer, ForeignKey("hospitals.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(
        Enum("equipment", "medicine", "blood_bank", "ppe", "oxygen", "consumable", name="resource_category"),
        nullable=False,
    )
    unit: Mapped[str] = mapped_column(String(50), nullable=False, default="units")
    total_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    minimum_threshold: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5,
        comment="Alert when available drops below this"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    usage_logs: Mapped[list["ResourceUsage"]] = relationship("ResourceUsage", back_populates="resource")

    def __repr__(self) -> str:
        return f"<Resource(id={self.id}, name='{self.name}', available={self.available_quantity})>"


class ResourceUsage(Base):
    """Log of resource consumption — tracks who used what and when."""

    __tablename__ = "resource_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_id: Mapped[int] = mapped_column(Integer, ForeignKey("resources.id"), nullable=False)
    admission_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("admissions.id"), nullable=True)

    quantity_used: Mapped[float] = mapped_column(Float, nullable=False)
    used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    resource: Mapped["Resource"] = relationship("Resource", back_populates="usage_logs")

    def __repr__(self) -> str:
        return f"<ResourceUsage(resource={self.resource_id}, qty={self.quantity_used})>"
