from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status
from jose import JWTError, jwt

from core.settings import settings
from models.enums import UserRole

ROLE_ORDER: dict[str, int] = {
    UserRole.staff.value: 1,
    UserRole.admin.value: 2,
    UserRole.owner.value: 3,
}


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: uuid.UUID
    firm_id: uuid.UUID
    role: UserRole


def decode_jwt_token(token: str) -> AuthenticatedUser:
    """
    Decode and validate a Cognito-issued JWT (modeled as HS256 here for simplicity).

    The token must include:
    - sub: user id
    - firm_id: tenant id
    - role: 'owner' | 'admin' | 'staff'
    """

    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    sub = payload.get("sub")
    firm_id_str = payload.get("firm_id")
    role_str = payload.get("role")

    if not sub or not firm_id_str or not role_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token claims")

    if role_str not in ROLE_ORDER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unknown role")

    try:
        user_id = uuid.UUID(sub)
        firm_id = uuid.UUID(firm_id_str)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid claim format") from exc

    role = UserRole(role_str)
    return AuthenticatedUser(user_id=user_id, firm_id=firm_id, role=role)


def ensure_minimum_role(user: AuthenticatedUser, *, minimum_role: UserRole) -> None:
    """
    Enforce role hierarchy: owner > admin > staff.
    """

    if ROLE_ORDER[user.role.value] < ROLE_ORDER[minimum_role.value]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

