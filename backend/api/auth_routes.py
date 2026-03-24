from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel

from auth.dependencies import get_current_firm, get_current_user, require_role
from auth.jwt import AuthenticatedUser
from core.settings import settings
from db import get_db
from models.enums import UserRole
from models.user import User
from jose import jwt as jose_jwt

import sqlalchemy as sa
from sqlalchemy.orm import Session

router = APIRouter()


# ---------------------------------------------------------------------------
# Login endpoint (demo / development)
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: str
    password: str  # In production, validate against Cognito; here we accept any non-empty password


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    firm_id: str
    role: str
    full_name: str | None


@router.post("/api/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """
    Development login: look up user by email, issue a signed JWT.
    In production this would validate against AWS Cognito.
    """
    if not payload.password:
        raise HTTPException(status_code=400, detail="Password is required")

    user = db.scalar(sa.select(User).where(User.email == payload.email, User.is_active == True))

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Issue JWT
    exp = datetime.now(timezone.utc) + timedelta(days=7)
    token_payload = {
        "sub": str(user.id),
        "firm_id": str(user.firm_id),
        "role": user.role.value if isinstance(user.role, UserRole) else user.role,
        "exp": int(exp.timestamp()),
    }
    access_token = jose_jwt.encode(token_payload, settings.jwt_secret, algorithm="HS256")

    return LoginResponse(
        access_token=access_token,
        user_id=str(user.id),
        firm_id=str(user.firm_id),
        role=user.role.value if isinstance(user.role, UserRole) else user.role,
        full_name=user.full_name,
    )


# ---------------------------------------------------------------------------
# Introspection
# ---------------------------------------------------------------------------

@router.get("/me")
def read_me(current_user: AuthenticatedUser = Depends(get_current_user)) -> dict[str, str]:
    """Simple introspection endpoint."""
    return {
        "user_id": str(current_user.user_id),
        "firm_id": str(current_user.firm_id),
        "role": current_user.role.value,
    }


@router.post("/firms/{firm_id}/example-action")
def firm_scoped_action(
    *,
    path_firm_id: uuid.UUID = Path(..., alias="firm_id"),
    current_user: AuthenticatedUser = Depends(require_role(UserRole.staff)),
    current_firm_id: str = Depends(get_current_firm),
) -> dict[str, str]:
    """
    Example endpoint showing strict tenant isolation.
    """
    if str(path_firm_id) != current_firm_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied")

    return {"status": "ok", "firm_id": current_firm_id}
