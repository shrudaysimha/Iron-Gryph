"""Case Management Router — Case Dashboard, Details, and Status Updates."""

import random
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from legal_system.app.database import get_db
from legal_system.app.models import Case, EvidenceDocument, User
from legal_system.app.schemas import CaseCreate, CaseResponse, CaseDetailResponse, CaseStatusUpdate
from legal_system.app.auth import get_current_user
from legal_system.app.audit_service import log_audit_event

router = APIRouter(prefix="/cases", tags=["Case Management"])


@router.get("", response_model=List[CaseResponse], include_in_schema=False)
@router.get("/", response_model=List[CaseResponse])
def list_cases(
    status_filter: Optional[str] = Query(None, alias="status"),
    category: Optional[str] = None,
    priority: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List investigation cases with optional filtering by status, category, priority, or search query.
    Accessible by both Investigators and Administrators.
    """
    query = db.query(Case)

    if status_filter and status_filter.lower() != "all":
        query = query.filter(Case.status == status_filter)

    if category:
        query = query.filter(Case.category == category)

    if priority:
        query = query.filter(Case.priority == priority)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Case.title.ilike(search_pattern),
                Case.case_number.ilike(search_pattern),
                Case.description.ilike(search_pattern),
            )
        )

    cases = query.order_by(Case.created_at.desc()).all()

    result = []
    for c in cases:
        resp = CaseResponse(
            id=c.id,
            case_number=c.case_number,
            title=c.title,
            description=c.description,
            category=c.category,
            status=c.status,
            priority=c.priority,
            lead_investigator_id=c.lead_investigator_id,
            lead_investigator_name=c.lead_investigator.full_name if c.lead_investigator else "Unassigned",
            document_count=len(c.evidence_documents),
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        result.append(resp)

    return result


@router.post("/", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    case_in: CaseCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new criminal or regulatory investigation case."""
    # Generate unique case number
    year = datetime.now().year
    random_id = random.randint(1000, 9999)
    case_number = f"CASE-{year}-{random_id}"

    # Verify uniqueness
    while db.query(Case).filter(Case.case_number == case_number).first():
        random_id = random.randint(1000, 9999)
        case_number = f"CASE-{year}-{random_id}"

    lead_id = case_in.lead_investigator_id or current_user.id
    lead_user = db.query(User).filter(User.id == lead_id).first()
    if not lead_user:
        raise HTTPException(status_code=400, detail="Invalid lead investigator ID")

    new_case = Case(
        case_number=case_number,
        title=case_in.title,
        description=case_in.description,
        category=case_in.category,
        priority=case_in.priority,
        lead_investigator_id=lead_id,
        status="Open",
    )
    db.add(new_case)
    db.commit()
    db.refresh(new_case)

    # Log audit event
    log_audit_event(
        db=db,
        action="CREATE_CASE",
        resource_type="Case",
        resource_id=new_case.case_number,
        details=f"Case '{new_case.title}' ({new_case.case_number}) initiated by {current_user.full_name}. Priority: {new_case.priority}",
        user=current_user,
        ip_address=request.client.host if request.client else "127.0.0.1",
    )

    return CaseResponse(
        id=new_case.id,
        case_number=new_case.case_number,
        title=new_case.title,
        description=new_case.description,
        category=new_case.category,
        status=new_case.status,
        priority=new_case.priority,
        lead_investigator_id=new_case.lead_investigator_id,
        lead_investigator_name=lead_user.full_name,
        document_count=0,
        created_at=new_case.created_at,
        updated_at=new_case.updated_at,
    )


@router.get("/{case_id}", response_model=CaseDetailResponse)
def get_case_detail(
    case_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve full details of a case, including its secured evidence vault documents."""
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Case not found")

    # Record access in audit log
    log_audit_event(
        db=db,
        action="VIEW_CASE",
        resource_type="Case",
        resource_id=c.case_number,
        details=f"{current_user.full_name} ({current_user.role}) accessed case vault for {c.case_number}",
        user=current_user,
        ip_address=request.client.host if request.client else "127.0.0.1",
    )

    ev_list = []
    for ev in c.evidence_documents:
        ev_list.append(
            {
                "id": ev.id,
                "case_id": ev.case_id,
                "title": ev.title,
                "description": ev.description,
                "category": ev.category,
                "original_filename": ev.original_filename,
                "file_size_bytes": ev.file_size_bytes,
                "mime_type": ev.mime_type,
                "sha256_hash": ev.sha256_hash,
                "uploaded_by_id": ev.uploaded_by_id,
                "uploader_name": ev.uploader.full_name if ev.uploader else "Unknown",
                "is_tampered": ev.is_tampered,
                "created_at": ev.created_at,
            }
        )

    return CaseDetailResponse(
        id=c.id,
        case_number=c.case_number,
        title=c.title,
        description=c.description,
        category=c.category,
        status=c.status,
        priority=c.priority,
        lead_investigator_id=c.lead_investigator_id,
        lead_investigator_name=c.lead_investigator.full_name if c.lead_investigator else "Unassigned",
        document_count=len(c.evidence_documents),
        created_at=c.created_at,
        updated_at=c.updated_at,
        evidence_documents=ev_list,
    )


@router.put("/{case_id}/status", response_model=CaseResponse)
def update_case_status(
    case_id: int,
    status_update: CaseStatusUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update case lifecycle status (Open, Under Investigation, In Court, Closed)."""
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Case not found")

    old_status = c.status
    c.status = status_update.status
    c.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(c)

    log_audit_event(
        db=db,
        action="UPDATE_CASE_STATUS",
        resource_type="Case",
        resource_id=c.case_number,
        details=f"Case status changed from '{old_status}' to '{c.status}' by {current_user.full_name}",
        user=current_user,
        ip_address=request.client.host if request.client else "127.0.0.1",
    )

    return CaseResponse(
        id=c.id,
        case_number=c.case_number,
        title=c.title,
        description=c.description,
        category=c.category,
        status=c.status,
        priority=c.priority,
        lead_investigator_id=c.lead_investigator_id,
        lead_investigator_name=c.lead_investigator.full_name if c.lead_investigator else "Unassigned",
        document_count=len(c.evidence_documents),
        created_at=c.created_at,
        updated_at=c.updated_at,
    )
