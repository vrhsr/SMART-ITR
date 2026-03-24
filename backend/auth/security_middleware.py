"""
Security and CORS middleware.

Phase 1B implementation:
  - SecurityHeadersMiddleware: adds HSTS, CSP, X-Frame-Options,
    Cache-Control: no-store to every response. Financial-grade defaults.
  - RequestIDMiddleware: injects a short X-Request-ID header so CA support
    tickets can be traced in CloudWatch within seconds.
  - PAN/Aadhaar scrubbing: applied in the global exception handler in main.py
    (not here, because we need access to the response body shaping logic).
"""
from __future__ import annotations

import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# ---------------------------------------------------------------------------
# Constants – regex for PII scrubbing (also used in main.py exception handler)
# ---------------------------------------------------------------------------
PAN_RE = re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]")
AADHAAR_RE = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")


def scrub_pii(text: str) -> str:
    """Replace PAN and Aadhaar patterns in any string. Used in error handlers."""
    text = PAN_RE.sub("**PAN_REDACTED**", text)
    text = AADHAAR_RE.sub("**AADHAAR_REDACTED**", text)
    return text


# ---------------------------------------------------------------------------
# Request ID middleware
# ---------------------------------------------------------------------------

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Inject a short unique ID into every request/response cycle.
    Stored on request.state.request_id so error responses can include it.
    Header: X-Request-ID
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add production security headers to every HTTP response.

    Cache-Control: no-store is applied globally because ALL responses
    contain financial data — we never want intermediate proxies or
    browser caches to store taxpayer information.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        # CSP intentionally avoids unsafe-inline — tighten further once
        # the frontend is audited for inline scripts.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "connect-src 'self' https://*.smartitr.in; "
            "frame-ancestors 'none'"
        )
        return response
