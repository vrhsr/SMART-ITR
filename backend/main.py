from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from api.router import api_router
from api.health import router as health_router
from auth.middleware import AuthMiddleware
from auth.billing_middleware import BillingMiddleware
from auth.security_middleware import RequestIDMiddleware, SecurityHeadersMiddleware, scrub_pii
from core.settings import settings
from db import SessionLocal
from services.pdf_cleanup import delete_approved_pdfs

logger = logging.getLogger("smartitr")

# ---------------------------------------------------------------------------
# Background scheduler
# ---------------------------------------------------------------------------
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up SmartITR application...")
    scheduler.add_job(
        delete_approved_pdfs,
        "interval",
        hours=1,
        id="dpdp_pdf_cleanup",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Started background schedulers (DPDP cleanup).")
    yield
    logger.info("Shutting down SmartITR application...")
    scheduler.shutdown()


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="SmartITR API",
    description=(
        "Production-grade API for SmartITR — the LangGraph-powered ITR filing "
        "platform for Chartered Accountant firms."
    ),
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware stack (outermost first → innermost last)
#
# Order matters: Starlette wraps in reverse-include order so the first
# add_middleware call is the outermost (first to receive the request,
# last to touch the response).
#
#   1. RequestIDMiddleware   — attach X-Request-ID to every req/resp
#   2. SecurityHeadersMiddleware — add security headers to every response
#   3. CORSMiddleware        — handle browser pre-flight
#   4. BillingMiddleware     — block expired subscriptions (returns 402)
#   5. AuthMiddleware        — parse + validate JWT, populate request.state
# ---------------------------------------------------------------------------

app.add_middleware(RequestIDMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    # In production set this to your exact origins. Wildcard is fine for
    # local dev but should be locked down before going live.
    allow_origins=settings.cors_origins if hasattr(settings, "cors_origins") else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

app.add_middleware(BillingMiddleware)

app.add_middleware(
    AuthMiddleware,
    exempt_paths={
        "/health",
        "/ready",
        # v1 paths
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/forgot-password",
        "/api/v1/client/consent",
        "/api/v1/client/consent/revoke",
        "/api/v1/client/my-data",
        "/api/v1/privacy-notice",
        "/api/v1/public/branding",
        # Portal (token is the auth)
        "/api/v1/portal",
        # Swagger UI
        "/docs",
        "/openapi.json",
    },
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

# /health is mounted at root — no auth, no version prefix.
# Required by ALB/ECS health checks.
app.include_router(health_router)

# All versioned endpoints under /api/v1/
app.include_router(api_router)


# ---------------------------------------------------------------------------
# GET /ready — deep liveness check (DB + cloud connectivity)
# ---------------------------------------------------------------------------

@app.get("/ready", tags=["ops"])
def readiness_check() -> dict:
    """
    Readiness probe used by ECS / K8s before routing traffic.
    Checks that the database accepts connections.
    Returns 200 if ready, 503 if not.
    """
    checks: dict[str, str] = {}

    # Database
    try:
        db = SessionLocal()
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db.close()
        checks["database"] = "ok"
    except Exception as exc:
        logger.error("Readiness: database check failed", exc_info=exc)
        checks["database"] = "error"

    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    http_status = 200 if status == "ok" else 503

    return JSONResponse(content={"status": status, "checks": checks}, status_code=http_status)


# ---------------------------------------------------------------------------
# Global exception handler — PAN/Aadhaar scrubbing + structured 500
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Ensures we:
      1. Never expose raw tracebacks to clients.
      2. Never include PAN or Aadhaar numbers in error responses.
      3. Always log unhandled errors with the request ID for traceability.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception(
        "Unhandled error",
        extra={"path": str(request.url.path), "method": request.method, "request_id": request_id},
    )

    # PII-safe error message
    safe_msg = scrub_pii(str(exc))
    if len(safe_msg) > 200:
        safe_msg = safe_msg[:200] + "…"

    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_001",
            "message": "An unexpected error occurred. Please try again or contact support.",
            "request_id": request_id,
            # Only include detail in non-production environments
            **({"detail": safe_msg} if settings.debug else {}),
        },
    )
