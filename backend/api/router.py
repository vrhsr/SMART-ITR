from __future__ import annotations

from fastapi import APIRouter

from api.auth_routes import router as auth_router
from api.billing import router as billing_router
from api.ca import router as ca_router
from api.client_privacy import router as client_privacy_router
from api.clients import router as clients_router
from api.document_read import router as document_read_router
from api.documents import router as documents_router
from api.exports import router as exports_router
from api.findings import router as findings_router
from api.health import router as health_router
from api.privacy_notice import router as privacy_router
from api.tax import router as tax_router

# -----------------------------------------------------------------
# All versioned endpoints live under /api/v1/.
# The health_router is mounted separately in main.py at the root so it
# remains available for load-balancer liveness probes at /health (no auth).
# -----------------------------------------------------------------

v1_router = APIRouter(prefix="/api/v1")

# Auth
v1_router.include_router(auth_router, prefix="/auth", tags=["auth"])

# Client management
v1_router.include_router(clients_router, prefix="/ca/clients", tags=["clients"])

# Document lifecycle
# Upload flow:  POST /upload-url, POST /confirm
v1_router.include_router(documents_router, prefix="/ca/documents", tags=["documents"])
# Read path:    GET list, detail, status polling, DELETE
v1_router.include_router(document_read_router, prefix="/ca/documents", tags=["documents"])

# Findings, exports, and tax computation (define their own sub-paths under /ca)
v1_router.include_router(findings_router, prefix="/ca", tags=["findings"])
v1_router.include_router(exports_router, prefix="/ca", tags=["exports"])
v1_router.include_router(tax_router, prefix="/ca", tags=["tax"])

# CA dashboard metrics
v1_router.include_router(ca_router, prefix="/ca", tags=["ca-dashboard"])

# Billing
v1_router.include_router(billing_router, prefix="/billing", tags=["billing"])

# Client (taxpayer) portal privacy endpoints
v1_router.include_router(client_privacy_router, prefix="/client", tags=["client-privacy"])

# Public / no-auth
v1_router.include_router(privacy_router, prefix="", tags=["privacy"])

# Expose as api_router so main.py import is unchanged
api_router = v1_router
