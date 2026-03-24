from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from db import SessionLocal
from models import Firm
from auth.jwt import AuthenticatedUser, decode_jwt_token


class BillingMiddleware:
    """
    Enforce subscription status with a 7-day grace period.
    """

    def __init__(self, app: Callable) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path") or ""
        if path.startswith("/api/billing/webhook") or path.startswith("/health"):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        auth_header = headers.get(b"authorization")
        if not auth_header:
            await self.app(scope, receive, send)
            return

        token = auth_header.decode().removeprefix("Bearer ").strip()
        user: AuthenticatedUser = decode_jwt_token(token)

        try:
            db = SessionLocal()
        except Exception:
            # If DB is unavailable, fail open rather than blocking all traffic.
            await self.app(scope, receive, send)
            return
        try:
            firm: Firm | None = db.scalar(select(Firm).where(Firm.firm_id == user.firm_id))
            if firm is None:
                await self.app(scope, receive, send)
                return

            now = datetime.now(timezone.utc)
            active_until = firm.current_period_end or firm.trial_ends_at

            if active_until is None:
                await self.app(scope, receive, send)
                return

            grace_end = active_until + timedelta(days=7)

            if now > grace_end:
                response = JSONResponse(
                    status_code=402,
                    content={"detail": "Your SmartITR subscription has expired. Please update billing to continue."},
                )
                await response(scope, receive, send)
                return

            async def send_with_warning(message):
                if message["type"] == "http.response.start" and now > active_until:
                    headers = message.setdefault("headers", [])
                    headers.append(
                        (b"x-smartitr-billing-warning", b"Subscription expired, within 7-day grace period.")
                    )
                await send(message)

            await self.app(scope, receive, send_with_warning)
        finally:
            db.close()

