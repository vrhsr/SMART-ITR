from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from auth.jwt import AuthenticatedUser, ensure_minimum_role
from models.enums import UserRole


def get_current_user(request: Request) -> AuthenticatedUser:
    """
    Retrieve the authenticated user placed on the request by AuthMiddleware.
    """

    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def get_current_firm(current_user: AuthenticatedUser = Depends(get_current_user)) -> str:
    """
    Dependency that exposes firm_id from the JWT.

    Never trust firm_id from request body or query parameters.
    """

    return str(current_user.firm_id)


def require_role(minimum_role: UserRole):
    """
    Dependency factory enforcing a minimum role.
    """

    def dependency(current_user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        ensure_minimum_role(current_user, minimum_role=minimum_role)
        return current_user

    return dependency

