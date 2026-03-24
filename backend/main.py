from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from api.router import api_router
from auth.middleware import AuthMiddleware
from auth.billing_middleware import BillingMiddleware
from core.settings import settings
from db import SessionLocal
from services.pdf_cleanup import delete_approved_pdfs

logger = logging.getLogger("smartitr")

# Setup Background Scheduler
scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up SmartITR application...")
    
    # Run DPDP PDF cleanup every hour
    scheduler.add_job(
        delete_approved_pdfs,
        'interval',
        hours=1,
        id='dpdp_pdf_cleanup',
        replace_existing=True
    )
    scheduler.start()
    logger.info("Started background schedulers (DPDP cleanup).")
    
    yield
    
    logger.info("Shutting down SmartITR application...")
    scheduler.shutdown()

app = FastAPI(
    title="Smart-ITR Backend Platform",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

app.add_middleware(
    AuthMiddleware,
    exempt_paths={
        "/health",
        "/api/auth/login",
        "/api/client/consent",
        "/api/client/consent/revoke",
        "/api/client/my-data",
        "/api/privacy-notice",
        "/docs",
        "/openapi.json",
    },
)
app.add_middleware(BillingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Ensure we never return 500 without logging.
    """

    logger.exception("Unhandled error", extra={"path": str(request.url.path), "method": request.method})
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

