from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from auth.middleware import AuthMiddleware
from auth.billing_middleware import BillingMiddleware
from api.router import api_router

logger = logging.getLogger("smartitr")

app = FastAPI(title="SmartITR API")
app.add_middleware(
    AuthMiddleware,
    exempt_paths={
        "/health",
        "/api/client/consent",
        "/api/client/consent/revoke",
        "/api/client/my-data",
        "/api/privacy-notice",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(BillingMiddleware)
app.include_router(api_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Ensure we never return 500 without logging.
    """

    logger.exception("Unhandled error", extra={"path": str(request.url.path), "method": request.method})
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

