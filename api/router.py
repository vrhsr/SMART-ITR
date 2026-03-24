from __future__ import annotations

from fastapi import APIRouter

from api.auth_routes import router as auth_router
from api.client_privacy import router as client_privacy_router
from api.billing import router as billing_router
from api.documents import router as documents_router
from api.document_status import router as document_status_router
from api.health import router as health_router
from api.privacy_notice import router as privacy_router
from api.ca import router as ca_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(documents_router)
api_router.include_router(document_status_router)
api_router.include_router(billing_router)
api_router.include_router(client_privacy_router)
api_router.include_router(privacy_router)
api_router.include_router(ca_router)

