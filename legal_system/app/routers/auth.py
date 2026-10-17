"""Authentication and User Management Router."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from legal_system.app.database import get_db
from legal_system.app.models import User
from legal_system.app.schemas import UserLogin, TokenResponse, UserResponse
from legal_system.app.auth import verify_password, create_access_token, get_current_user, require_admin
from legal_system.app.audit_service import log_audit_event

router = APIRouter(prefix="/auth", tags=["Authentication & RBAC"])


@router.post("/login", response_model=TokenResponse)
def login(login_data: UserLogin, request: Request, db: Session = Depends(get_db)):
    """Authenticate user with username and password, return JWT with role claims."""
    user = db.query(User).filter(User.username == login_data.username).first()
    if not user or not verify_password(login_data.password, user.password_hash, user.password_salt):
        # Log failed attempt
        log_audit_event(
            db=db,
            action="LOGIN_FAILED",
            resource_type="User",
            details=f"Failed login attempt for username: {login_data.username}",
            ip_address=request.client.host if request.client else "127.0.0.1",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact Administrator.",
        )

    token = create_access_token(
        data={"sub": user.username, "role": user.role, "id": user.id, "name": user.full_name}
    )

    log_audit_event(
        db=db,
        action="LOGIN_SUCCESS",
        resource_type="User",
        resource_id=str(user.id),
        details=f"User {user.full_name} ({user.badge_number}) authenticated as {user.role.upper()}",
        user=user,
        ip_address=request.client.host if request.client else "127.0.0.1",
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user,
    }


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Return currently authenticated user profile and active role."""
    return current_user


@router.get("/users", response_model=List[UserResponse])
def list_users(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all investigators and administrators (Admin Only)."""
    return db.query(User).all()
