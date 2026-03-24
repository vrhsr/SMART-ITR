from __future__ import annotations

from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from auth.jwt import AuthenticatedUser, decode_jwt_token


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Extract and validate JWT on every request, attaching the authenticated user
    to request.state.user for downstream dependencies.
    """

    def __init__(self, app: Callable, *, exempt_paths: set[str] | None = None) -> None:
        super().__init__(app)
        self._exempt_paths = exempt_paths or {"/health"}

    async def dispatch(self, request: Request, call_next: Callable) -> JSONResponse:
        if request.url.path in self._exempt_paths:
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Missing bearer token"})

        token = auth_header.removeprefix("Bearer ").strip()
        user: AuthenticatedUser
        try:
            user = decode_jwt_token(token)
        except Exception as exc:  # auth functions already raise HTTPException
            if hasattr(exc, "status_code"):
                return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})

        request.state.user = user
        return await call_next(request)

