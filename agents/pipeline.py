from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.state import ProcessingState
from core.settings import settings
from db import SessionLocal
from engine.tax_calculator import calculate_tax_liability_paise
from models import AuditEvent, Document
from services.bedrock import haiku_classify_document, sonnet_explain_anomalies
from services.s3_documents import download_pdf_to_memory
from services.textract import textract_analyze_tables, textract_detect_text
from services.extractor import extract_form16_fields, extract_bank_statement_transactions, extract_ais_entries
from engine.field_mapper import map_extracted_fields_to_income_data
from services.exporter import generate_excel_export, generate_itd_json, generate_client_pdf_report

logger = logging.getLogger("smartitr")


def _load_document(db: Session, *, document_id: str, firm_id: str) -> Document:
    document = db.scalar(
        select(Document).where(Document.id == document_id, Document.firm_id == firm_id),
    )
    if document is None:
        raise ValueError("Document not found for firm")
    return document


def node_classify_document(state: ProcessingState) -> ProcessingState:
    """
    NODE 1: classify_document
    """

    db = SessionLocal()
    try:
        doc = _load_document(db, document_id=state.document_id, firm_id=state.firm_id)
        pdf_bytes = download_pdf_to_memory(bucket=doc.s3_bucket, key=doc.s3_key)
        raw_text = textract_detect_text(pdf_bytes=pdf_bytes)
        doc_type = haiku_classify_document(raw_text=raw_text)
        state.raw_text = raw_text
        state.doc_type = doc_type
        state.status = "classified"
        return state
    finally:
        db.close()


def node_extract_fields(state: ProcessingState) -> ProcessingState:
    """
    NODE 2: extract_fields
    """

    db = SessionLocal()
    try:
        doc = _load_document(db, document_id=state.document_id, firm_id=state.firm_id)
        pdf_bytes = download_pdf_to_memory(bucket=doc.s3_bucket, key=doc.s3_key)

        extracted: dict[str, Any] = {}
        findings: list[dict[str, Any]] = list(state.validation_findings)
        raw_text = state.raw_text or ""

        if state.doc_type == "form16":
            tables = textract_analyze_tables(pdf_bytes=pdf_bytes)
            result = extract_form16_fields(raw_text=raw_text, tables=tables)
            extracted = {"form16": result.data, "confidence": result.confidence}
        elif state.doc_type == "bank_statement":
            result = extract_bank_statement_transactions(raw_text=raw_text)
            extracted = {"bank_statement": result.data, "confidence": result.confidence}
        elif state.doc_type in ("ais", "26as", "capital_gains"):
            result = extract_ais_entries(raw_text=raw_text)
            extracted = {"ais": result.data, "confidence": result.confidence}
        else:
            extracted = {"confidence": 0.0}
            findings.append({"type": "unknown_doc_type", "message": "Document type unknown", "severity": "warning"})

        # Flag low-confidence fields for CA review
        confidence = float(extracted.get("confidence", 0.0))
        if confidence < 0.85:
            findings.append({"type": "low_confidence", "message": "Low confidence extraction. Manual review required.", "severity": "info"})

        state.extracted_fields = extracted
        state.validation_findings = findings
        state.status = "extracted"
        return state
    finally:
        db.close()


def node_validate_cross_doc(state: ProcessingState) -> ProcessingState:
    """
    NODE 3: validate_cross_doc (pure Python)
    """

    findings = list(state.validation_findings)
    extracted = state.extracted_fields or {}
    
    form16 = extracted.get("form16", {})
    ais = extracted.get("ais", {})
    bank = extracted.get("bank_statement", {})
    
    f16_salary = form16.get("gross_salary_paise", 0)
    ais_salary = ais.get("salary_as_reported_paise", 0)
    
    if f16_salary > 0 and ais_salary > 0:
        delta = abs(f16_salary - ais_salary)
        if delta > 1000 * 100: # 1,000 rupees mismatch threshold
            findings.append({
                "type": "mismatch_salary",
                "message": f"AIS salary (₹{ais_salary//100}) differs from Form 16 salary (₹{f16_salary//100}) by more than ₹1,000.",
                "severity": "high",
                "details": {"ais_paise": ais_salary, "form16_paise": f16_salary, "delta_paise": delta}
            })

    state.validation_findings = findings
    state.status = "validated"
    return state


def node_calculate_tax(state: ProcessingState) -> ProcessingState:
    """
    NODE 4: calculate_tax (deterministic Python only)
    """

    extracted = state.extracted_fields or {}
    income_data = map_extracted_fields_to_income_data(extracted)
    
    # Calculate tax based on mapped extraction
    try:
        from engine.tax_calculator import compare_regimes
        comparison = compare_regimes(income_data)
        state.tax_computation = {
            "old_regime_tax_paise": comparison["old_tax"],
            "new_regime_tax_paise": comparison["new_tax"],
            "recommended_regime": comparison["recommended_regime"],
            "savings_paise": comparison["savings"],
            "income_data_used": income_data
        }
    except Exception as e:
        logger.error(f"Tax calculation failed: {e}")
        state.tax_computation = {
            "error": str(e),
            "old_regime_tax_paise": 0,
            "new_regime_tax_paise": 0,
            "recommended_regime": "unknown",
            "savings_paise": 0
        }

    state.status = "calculated"
    return state


def node_check_anomalies(state: ProcessingState) -> ProcessingState:
    """
    NODE 5: check_anomalies
    """

    if not state.validation_findings:
        state.status = "anomalies_skipped"
        return state

    explanation = sonnet_explain_anomalies(findings=state.validation_findings)
    state.anomalies = [{"explanation": explanation}]
    state.status = "anomalies_checked"
    return state


def node_prepare_export(state: ProcessingState) -> ProcessingState:
    """
    NODE 6: prepare_export
    """

    try:
        db = SessionLocal()
        doc = _load_document(db, document_id=state.document_id, firm_id=state.firm_id)
        doc.status = "ready_for_review"

        event = AuditEvent(
            firm_id=doc.firm_id,
            action="pipeline.completed",
            resource_type="document",
            resource_id=str(doc.id),
            details={"findings_count": len(state.validation_findings)},
        )
        db.add(event)
        
        # Save validation findings to DB
        for f in state.validation_findings:
            from models.validation_finding import ValidationFinding
            finding = ValidationFinding(
                firm_id=doc.firm_id,
                document_id=doc.id,
                finding_type=f.get("type", "unknown"),
                severity=f.get("severity", "info"),
                message=f.get("message", ""),
                details=f.get("details", {})
            )
            db.add(finding)

        db.commit()
    finally:
        db.close()

    state.status = "done"
    return state


def _on_error(state: ProcessingState, exc: Exception) -> ProcessingState:
    state.status = "failed"
    state.error = str(exc)
    logger.exception("Pipeline failed", extra={"document_id": state.document_id, "firm_id": state.firm_id})
    return state


def build_processing_graph() -> Any:
    """
    Build and return the LangGraph processing pipeline.
    """

    graph = StateGraph(ProcessingState)
    graph.add_node("classify_document", node_classify_document)
    graph.add_node("extract_fields", node_extract_fields)
    graph.add_node("validate_cross_doc", node_validate_cross_doc)
    graph.add_node("calculate_tax", node_calculate_tax)
    graph.add_node("check_anomalies", node_check_anomalies)
    graph.add_node("prepare_export", node_prepare_export)

    graph.set_entry_point("classify_document")
    graph.add_edge("classify_document", "extract_fields")
    graph.add_edge("extract_fields", "validate_cross_doc")
    graph.add_edge("validate_cross_doc", "calculate_tax")
    graph.add_edge("calculate_tax", "check_anomalies")
    graph.add_edge("check_anomalies", "prepare_export")
    graph.add_edge("prepare_export", END)

    return graph.compile()


def run_document_pipeline(*, document_id: str, firm_id: str, s3_key: str) -> ProcessingState:
    """
    Run the processing pipeline for a document.
    """

    app = build_processing_graph()
    state = ProcessingState(document_id=document_id, firm_id=firm_id, s3_key=s3_key)
    try:
        final = app.invoke(state)
        return ProcessingState.model_validate(final)
    except Exception as exc:
        return _on_error(state, exc)

