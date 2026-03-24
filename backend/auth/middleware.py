from __future__ import annotations

import json
from typing import Callable

from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.responses import JSONResponse

from auth.jwt import decode_jwt_token
from core.settings import settings


class AuthMiddleware:
    """
    Pure ASGI Middleware for JWT validation.
    Avoids BaseHTTPMiddleware to prevent issues with CORS headers on early returns.
    """

    def __init__(self, app: ASGIApp, *, exempt_paths: set[str] | None = None) -> None:
        self.app = app
        self._exempt_paths = exempt_paths or {"/health"}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Testing bypass (requires environment='test' and certain header)
        # This allows dependency_overrides to work without valid JWTs.
        env = getattr(settings, "environment", "dev")
        
        skip_header = None
        for name, value in scope["headers"]:
            if name == b"x-test-skip-auth": # Headers are typically lowercased
                skip_header = value.decode("latin-1")
                break

        if env == "test" and skip_header == "true":
            await self.app(scope, receive, send)
            return

        print(f"DEBUG AUTH: env={env}, skip={skip_header}, path={scope['path']}")
        # Bypass for preflight and exempt paths
        if scope["method"] == "OPTIONS" or scope["path"] in self._exempt_paths:
            await self.app(scope, receive, send)
            return

        # Extract Authorization header
        auth_header = None
        for name, value in scope["headers"]:
            if name == b"authorization":
                auth_header = value.decode("latin-1")
                break

        if not auth_header or not auth_header.startswith("Bearer "):
            response = JSONResponse(status_code=401, content={"detail": "Missing bearer token"})
            await response(scope, receive, send)
            return

        token = auth_header.removeprefix("Bearer ").strip()
        try:
            user = decode_jwt_token(token)
            # Attach user to scope (standard FastAPI/Starlette way)
            scope["state"] = scope.get("state", {})
            scope["state"]["user"] = user
        except Exception as exc:
            status_code = getattr(exc, "status_code", 401)
            detail = getattr(exc, "detail", "Invalid token")
            response = JSONResponse(status_code=status_code, content={"detail": detail})
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
