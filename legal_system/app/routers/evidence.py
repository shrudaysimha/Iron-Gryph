"""Evidence Vault Router — Cryptographic SHA-256 Storage, Upload, and Tamper Verification."""

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from legal_system.app.config import settings
from legal_system.app.database import get_db
from legal_system.app.models import Case, EvidenceDocument, User
from legal_system.app.schemas import EvidenceResponse, EvidenceVerifyResponse
from legal_system.app.auth import get_current_user
from legal_system.app.hashing import (
    compute_sha256,
    compute_file_sha256,
    verify_file_integrity,
    simulate_file_tamper,
)
from legal_system.app.audit_service import log_audit_event

router = APIRouter(prefix="/evidence", tags=["Evidence Vault & Integrity"])


@router.post("/upload", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    request: Request,
    case_id: int = Form(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    category: str = Form("Forensic Report"),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Secure Evidence Ingress:
    1. Ingests evidence binary stream.
    2. Computes immutable cryptographic SHA-256 digest at intake.
    3. Persists file to secured evidence vault storage.
    4. Writes immutable chain-of-custody audit log entry with SHA-256 fingerprint.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Target case not found")

    # Read binary content into memory
    content = await file.read()
    file_size = len(content)
    if file_size == 0:
        raise HTTPException(status_code=400, detail="Cannot ingest empty file")

    # Compute SHA-256 hash immediately
    sha256_digest = compute_sha256(content)

    # Unique storage name preserving original extension
    timestamp_prefix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    clean_filename = Path(file.filename or "evidence.bin").name.replace(" ", "_")
    stored_filename = f"CASE_{case.case_number}_{timestamp_prefix}_{clean_filename}"
    storage_path = Path(settings.upload_dir) / stored_filename

    # Save to disk
    with open(storage_path, "wb") as f:
        f.write(content)

    # Backup original for restore/tamper demo verification
    backup_path = Path(settings.upload_dir) / f"{stored_filename}.canonical_bak"
    with open(backup_path, "wb") as f:
        f.write(content)

    # Create DB entry
    evidence = EvidenceDocument(
        case_id=case.id,
        title=title,
        description=description,
        category=category,
        original_filename=file.filename or "evidence.bin",
        stored_filename=stored_filename,
        file_size_bytes=file_size,
        mime_type=file.content_type or "application/octet-stream",
        sha256_hash=sha256_digest,
        original_sha256_hash=sha256_digest,
        uploaded_by_id=current_user.id,
        is_tampered=False,
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    # Log chain of custody event
    log_audit_event(
        db=db,
        action="UPLOAD_EVIDENCE",
        resource_type="Evidence",
        resource_id=str(evidence.id),
        details=(
            f"Exhibit '{evidence.title}' ({evidence.original_filename}, {file_size} bytes) "
            f"deposited into {case.case_number}. Cryptographic seal: {sha256_digest[:16]}..."
        ),
        sha256_snapshot=sha256_digest,
        user=current_user,
        ip_address=request.client.host if request.client else "127.0.0.1",
    )

    return EvidenceResponse(
        id=evidence.id,
        case_id=evidence.case_id,
        title=evidence.title,
        description=evidence.description,
        category=evidence.category,
        original_filename=evidence.original_filename,
        file_size_bytes=evidence.file_size_bytes,
        mime_type=evidence.mime_type,
        sha256_hash=evidence.sha256_hash,
        uploaded_by_id=evidence.uploaded_by_id,
        uploader_name=current_user.full_name,
        is_tampered=evidence.is_tampered,
        created_at=evidence.created_at,
    )


@router.get("/{evidence_id}", response_model=EvidenceResponse)
def get_evidence_metadata(
    evidence_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve metadata and cryptographic hash for an evidence exhibit."""
    evidence = db.query(EvidenceDocument).filter(EvidenceDocument.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")

    log_audit_event(
        db=db,
        action="VIEW_EVIDENCE",
        resource_type="Evidence",
        resource_id=str(evidence.id),
        details=f"Viewed metadata for exhibit '{evidence.title}' in case #{evidence.case_id}",
        sha256_snapshot=evidence.sha256_hash,
        user=current_user,
        ip_address=request.client.host if request.client else "127.0.0.1",
    )

    return EvidenceResponse(
        id=evidence.id,
        case_id=evidence.case_id,
        title=evidence.title,
        description=evidence.description,
        category=evidence.category,
        original_filename=evidence.original_filename,
        file_size_bytes=evidence.file_size_bytes,
        mime_type=evidence.mime_type,
        sha256_hash=evidence.sha256_hash,
        uploaded_by_id=evidence.uploaded_by_id,
        uploader_name=evidence.uploader.full_name if evidence.uploader else "Unknown",
        is_tampered=evidence.is_tampered,
        created_at=evidence.created_at,
    )


@router.get("/{evidence_id}/download")
def download_evidence(
    evidence_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stream download the evidence exhibit. Records action in audit trail."""
    evidence = db.query(EvidenceDocument).filter(EvidenceDocument.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")

    storage_path = Path(settings.upload_dir) / evidence.stored_filename
    if not storage_path.exists():
        raise HTTPException(status_code=404, detail="Physical evidence file missing on disk")

    log_audit_event(
        db=db,
        action="DOWNLOAD_EVIDENCE",
        resource_type="Evidence",
        resource_id=str(evidence.id),
        details=f"Downloaded exhibit file '{evidence.original_filename}'",
        sha256_snapshot=evidence.sha256_hash,
        user=current_user,
        ip_address=request.client.host if request.client else "127.0.0.1",
    )

    return FileResponse(
        path=str(storage_path),
        filename=evidence.original_filename,
        media_type=evidence.mime_type,
    )


@router.post("/{evidence_id}/verify", response_model=EvidenceVerifyResponse)
def verify_evidence_hash(
    evidence_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    On-Demand Cryptographic Integrity Verification:
    Recomputes live SHA-256 hash from physical disk storage and compares against canonical seal.
    Returns Green Shield on match or Red Warning Shield on alteration.
    """
    evidence = db.query(EvidenceDocument).filter(EvidenceDocument.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")

    storage_path = Path(settings.upload_dir) / evidence.stored_filename
    integrity_result = verify_file_integrity(storage_path, evidence.original_sha256_hash)

    # Update database flag based on physical verification
    is_valid = integrity_result["is_valid"]
    evidence.is_tampered = not is_valid
    evidence.sha256_hash = integrity_result["current_hash"] or evidence.sha256_hash
    db.commit()
    db.refresh(evidence)

    # Log verification outcome
    action_type = "VERIFY_HASH_VALID" if is_valid else "TAMPER_ALERT"
    details_text = (
        f"Cryptographic integrity confirmed. SHA-256 matched: {integrity_result['expected_hash'][:16]}..."
        if is_valid
        else f"TAMPER ALERT! Expected: {integrity_result['expected_hash'][:16]}... vs Found: {str(integrity_result['current_hash'])[:16]}..."
    )

    log_audit_event(
        db=db,
        action=action_type,
        resource_type="Evidence",
        resource_id=str(evidence.id),
        details=details_text,
        sha256_snapshot=integrity_result["current_hash"],
        user=current_user,
        ip_address=request.client.host if request.client else "127.0.0.1",
    )

    return EvidenceVerifyResponse(
        evidence_id=evidence.id,
        title=evidence.title,
        filename=evidence.original_filename,
        is_valid=is_valid,
        expected_hash=integrity_result["expected_hash"],
        current_hash=integrity_result["current_hash"],
        status_badge=integrity_result["status_badge"],
        message=integrity_result["message"],
        verified_at=datetime.now(timezone.utc),
        verified_by=current_user.full_name,
    )


@router.post("/{evidence_id}/simulate-tamper", response_model=EvidenceVerifyResponse)
def simulate_evidence_tamper(
    evidence_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Demonstration / Penetration Test Endpoint:
    Simulates unauthorized tampering by modifying bytes on disk.
    Allows user to test the Red Warning Shield and instant audit alarm.
    """
    evidence = db.query(EvidenceDocument).filter(EvidenceDocument.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")

    storage_path = Path(settings.upload_dir) / evidence.stored_filename
    if not storage_path.exists():
        raise HTTPException(status_code=404, detail="Physical evidence file missing on disk")

    # Modify file bytes
    corrupt_hash = simulate_file_tamper(storage_path)
    evidence.is_tampered = True
    evidence.sha256_hash = corrupt_hash
    db.commit()
    db.refresh(evidence)

    log_audit_event(
        db=db,
        action="TAMPER_SIMULATION",
        resource_type="Evidence",
        resource_id=str(evidence.id),
        details=(
            f"TAMPER SIMULATION triggered by {current_user.full_name}. File bytes modified on disk. "
            f"New corrupted hash: {corrupt_hash[:16]}..."
        ),
        sha256_snapshot=corrupt_hash,
        user=current_user,
        ip_address=request.client.host if request.client else "127.0.0.1",
    )

    return EvidenceVerifyResponse(
        evidence_id=evidence.id,
        title=evidence.title,
        filename=evidence.original_filename,
        is_valid=False,
        expected_hash=evidence.original_sha256_hash,
        current_hash=corrupt_hash,
        status_badge="TAMPERED_RED",
        message="CRITICAL ALERT: File hash mismatch! Unauthorized modification detected.",
        verified_at=datetime.now(timezone.utc),
        verified_by=current_user.full_name,
    )


@router.post("/{evidence_id}/restore", response_model=EvidenceVerifyResponse)
def restore_evidence_integrity(
    evidence_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Restores the canonical uncorrupted file content from secure backup,
    bringing the evidence back to a Verified Green Shield state.
    """
    evidence = db.query(EvidenceDocument).filter(EvidenceDocument.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")

    storage_path = Path(settings.upload_dir) / evidence.stored_filename
    backup_path = Path(settings.upload_dir) / f"{evidence.stored_filename}.canonical_bak"

    if not backup_path.exists():
        raise HTTPException(status_code=400, detail="Canonical backup not found")

    with open(backup_path, "rb") as f_bak:
        canonical_bytes = f_bak.read()

    with open(storage_path, "wb") as f_dst:
        f_dst.write(canonical_bytes)

    clean_hash = compute_sha256(canonical_bytes)
    evidence.is_tampered = False
    evidence.sha256_hash = clean_hash
    db.commit()
    db.refresh(evidence)

    log_audit_event(
        db=db,
        action="RESTORE_INTEGRITY",
        resource_type="Evidence",
        resource_id=str(evidence.id),
        details=f"Evidence file restored to canonical state by {current_user.full_name}. SHA-256 seal valid.",
        sha256_snapshot=clean_hash,
        user=current_user,
        ip_address=request.client.host if request.client else "127.0.0.1",
    )

    return EvidenceVerifyResponse(
        evidence_id=evidence.id,
        title=evidence.title,
        filename=evidence.original_filename,
        is_valid=True,
        expected_hash=evidence.original_sha256_hash,
        current_hash=clean_hash,
        status_badge="VERIFIED_GREEN",
        message="Cryptographic seal matches canonical record. Chain of custody intact.",
        verified_at=datetime.now(timezone.utc),
        verified_by=current_user.full_name,
    )
