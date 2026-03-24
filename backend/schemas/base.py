"""
Shared Pydantic response and error schemas.

Build each endpoint-specific schema alongside its endpoint.
These are the ONLY schemas built upfront because they are
referenced across many different routers.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Generic paginated list wrapper
# ---------------------------------------------------------------------------

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    per_page: int
    total_pages: int


# ---------------------------------------------------------------------------
# Standardised error envelope
# ---------------------------------------------------------------------------

class ErrorDetail(BaseModel):
    error_code: str
    message: str
    request_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Standard error codes
# Searchable prefixes:
#   AUTH_  – authentication / authorisation
#   TENANT_– firm / subscription
#   DOC_   – document lifecycle
#   CLIENT_– client management
#   BILLING_ – payments
#   DPDP_  – consent / data-rights
# ---------------------------------------------------------------------------

class ErrorCodes:
    # Auth
    AUTH_001 = "AUTH_001"   # Invalid credentials
    AUTH_002 = "AUTH_002"   # Token expired
    AUTH_003 = "AUTH_003"   # Insufficient permissions
    AUTH_004 = "AUTH_004"   # User not found

    # Tenant / firm
    TENANT_001 = "TENANT_001"  # Firm not found
    TENANT_002 = "TENANT_002"  # Subscription expired
    TENANT_003 = "TENANT_003"  # Cross-tenant access attempt

    # Documents
    DOC_001 = "DOC_001"  # Document not found
    DOC_002 = "DOC_002"  # Document belongs to another firm
    DOC_003 = "DOC_003"  # Upload failed
    DOC_004 = "DOC_004"  # Processing failed
    DOC_005 = "DOC_005"  # Document not yet processed

    # Clients
    CLIENT_001 = "CLIENT_001"  # Client not found
    CLIENT_002 = "CLIENT_002"  # Duplicate PAN in this firm

    # Billing
    BILLING_001 = "BILLING_001"  # Payment failed
    BILLING_002 = "BILLING_002"  # No active subscription

    # DPDP / consent
    DPDP_001 = "DPDP_001"  # Consent not given

    # Upload portal
    PORTAL_001 = "PORTAL_001"  # Invalid or expired portal token
    PORTAL_002 = "PORTAL_002"  # Token upload limit exceeded


# ---------------------------------------------------------------------------
# Convenience factory used by endpoint handlers
# ---------------------------------------------------------------------------

def make_error(error_code: str, message: str, request_id: str | None = None) -> dict:
    return {"error_code": error_code, "message": message, "request_id": request_id}
