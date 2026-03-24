from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ProcessingState(BaseModel):
    document_id: str
    firm_id: str
    s3_key: str

    doc_type: Optional[str] = None  # form16, ais, 26as, bank_statement, capital_gains, unknown
    raw_text: Optional[str] = None
    extracted_fields: Optional[dict[str, Any]] = None
    validation_findings: list[dict[str, Any]] = Field(default_factory=list)
    tax_computation: Optional[dict[str, Any]] = None
    anomalies: list[dict[str, Any]] = Field(default_factory=list)
    status: str = "pending"
    error: Optional[str] = None

