"""SQLAlchemy ORM models for Legal & Investigation Document Management System."""

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from legal_system.app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    badge_number = Column(String(50), unique=True, nullable=False)
    role = Column(String(20), nullable=False, default="investigator")  # "administrator" or "investigator"
    password_hash = Column(String(128), nullable=False)
    password_salt = Column(String(64), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    assigned_cases = relationship("Case", back_populates="lead_investigator")
    uploaded_evidence = relationship("EvidenceDocument", back_populates="uploader")


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    case_number = Column(String(50), unique=True, index=True, nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False, default="Criminal Investigation")
    status = Column(String(30), nullable=False, default="Open")  # Open, Under Investigation, In Court, Closed
    priority = Column(String(20), nullable=False, default="Medium")  # Critical, High, Medium, Low
    lead_investigator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    lead_investigator = relationship("User", back_populates="assigned_cases")
    evidence_documents = relationship("EvidenceDocument", back_populates="case", cascade="all, delete-orphan")


class EvidenceDocument(Base):
    __tablename__ = "evidence_documents"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False, default="Forensic Report")
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    sha256_hash = Column(String(64), nullable=False, index=True)  # Recorded cryptographic seal
    original_sha256_hash = Column(String(64), nullable=False)     # Permanent immutable seal at intake
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_tampered = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    case = relationship("Case", back_populates="evidence_documents")
    uploader = relationship("User", back_populates="uploaded_evidence")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String(50), nullable=False)
    user_role = Column(String(20), nullable=False)
    action = Column(String(50), nullable=False, index=True)  # LOGIN, UPLOAD_EVIDENCE, VIEW_EVIDENCE, VERIFY_HASH, TAMPER_ALERT, etc.
    resource_type = Column(String(50), nullable=False)        # Case, Evidence, User, System
    resource_id = Column(String(50), nullable=True)
    details = Column(Text, nullable=False)
    sha256_snapshot = Column(String(64), nullable=True)
    ip_address = Column(String(50), default="127.0.0.1")
