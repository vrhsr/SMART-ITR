from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Path, status

from auth.dependencies import get_current_firm, get_current_user, require_role
from auth.jwt import AuthenticatedUser
from models.enums import UserRole

router = APIRouter()


@router.get("/me")
def read_me(current_user: AuthenticatedUser = Depends(get_current_user)) -> dict[str, str]:
    """
    Simple introspection endpoint.
    """

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

    The only trusted firm_id is the one from JWT (current_firm_id);
    the path parameter must match it or the request is rejected.
    """

    if str(path_firm_id) != current_firm_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied")

    return {"status": "ok", "firm_id": current_firm_id}

